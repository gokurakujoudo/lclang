"""Low-precedence comparison, Boolean, coalescing, and conditional parsing."""

from __future__ import annotations

from collections.abc import Callable

from pylcl.ast import (
    LclAstNode,
    LclBoolean,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclUnary,
)
from pylcl.ast.operators import BooleanOperator, ComparisonOperator, UnaryOperator
from pylcl.lang.lexer import TokenKind
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceSpan

_SINGLE_COMPARISONS = {
    TokenKind.LESS: ComparisonOperator.LESS,
    TokenKind.LESS_EQUAL: ComparisonOperator.LESS_EQUAL,
    TokenKind.GREATER: ComparisonOperator.GREATER,
    TokenKind.GREATER_EQUAL: ComparisonOperator.GREATER_EQUAL,
    TokenKind.EQUAL_EQUAL: ComparisonOperator.EQUAL,
    TokenKind.NOT_EQUAL: ComparisonOperator.NOT_EQUAL,
    TokenKind.KW_IN: ComparisonOperator.IN,
}


class _LogicalParser:
    """Parse the low-precedence logical expression layers.

    .. note::
       Each method delegates to the next tighter layer, preserving the grammar
       precedence while constructing immutable semantic AST nodes.
    """

    def __init__(
        self,
        stream: TokenStream,
        parse_arithmetic: Callable[[], LclAstNode],
        *,
        allow_conditional: bool,
    ) -> None:
        """Bind the token stream and arithmetic-layer callback.

        :param stream: Token stream positioned at the first logical operand.
        :param parse_arithmetic: Callback parsing one tighter arithmetic
           expression.
        :param allow_conditional: Whether trailing conditional syntax is
           permitted.
        :returns: ``None``.

        .. note::
           Conditional parsing is disabled for nested contexts that must stop
           before the complete-expression conditional layer.
        """
        self.stream = stream
        self.parse_arithmetic = parse_arithmetic
        self.allow_conditional = allow_conditional

    def parse(self) -> LclAstNode:
        """Parse the logical expression layer selected by configuration.

        :returns: Parsed conditional or coalescing/logical/comparison AST node.

        .. note::
           The conditional branch is selected only when ``allow_conditional``
           is true; all other calls begin at null coalescing.
        """
        return self._conditional() if self.allow_conditional else self._coalesce()

    def _conditional(self) -> LclAstNode:
        """Parse a right-associative conditional expression.

        :returns: Conditional AST node, or the coalescing operand when no
           ``if`` token is present.

        .. note::
           The false branch recurses through this method so chained
           conditionals associate from right to left.
        """
        when_true = self._coalesce()
        if self.stream.match(TokenKind.KW_IF) is None:
            return when_true
        condition = self._coalesce()
        self.stream.expect(TokenKind.KW_ELSE, "conditional expression requires else")
        when_false = self._conditional()
        return LclConditional(
            when_true,
            condition,
            when_false,
            span=_merge_span(when_true.span, when_false.span),
        )

    def _coalesce(self) -> LclAstNode:
        """Parse a right-associative null-coalescing expression.

        :returns: Coalescing AST node, or the Boolean operand when no ``??``
           token is present.

        .. note::
           The right operand recurses through coalescing to preserve its
           defined right association.
        """
        left = self._or()
        if self.stream.match(TokenKind.DOUBLE_QUESTION) is None:
            return left
        right = self._coalesce()
        return LclCoalesce(left, right, span=_merge_span(left.span, right.span))

    def _or(self) -> LclAstNode:
        """Parse the Boolean ``or`` layer.

        :returns: Boolean ``or`` AST node or its unchanged operand.

        .. note::
           Operand parsing is delegated to the tighter ``and`` layer.
        """
        return self._boolean(TokenKind.KW_OR, BooleanOperator.OR, self._and)

    def _and(self) -> LclAstNode:
        """Parse the Boolean ``and`` layer.

        :returns: Boolean ``and`` AST node or its unchanged operand.

        .. note::
           Operand parsing is delegated to the tighter unary-not layer.
        """
        return self._boolean(TokenKind.KW_AND, BooleanOperator.AND, self._not)

    def _boolean(
        self,
        kind: TokenKind,
        operator: BooleanOperator,
        operand: Callable[[], LclAstNode],
    ) -> LclAstNode:
        """Parse one repeated Boolean operator and its operands.

        :param kind: Token kind separating repeated Boolean operands.
        :param operator: Semantic operator stored in the resulting AST node.
        :param operand: Callback parsing one tighter operand.
        :returns: Boolean AST node, or the first operand when no separator is
           present.

        .. note::
           All operands are retained in source order for the evaluator's
           value-preserving short-circuit behavior.
        """
        first = operand()
        if self.stream.match(kind) is None:
            return first
        values = [first, operand()]
        while self.stream.match(kind) is not None:
            values.append(operand())
        return LclBoolean(
            operator,
            tuple(values),
            span=_merge_span(values[0].span, values[-1].span),
        )

    def _not(self) -> LclAstNode:
        """Parse recursively nested unary ``not`` operators.

        :returns: Unary-not AST node or the comparison operand unchanged.

        .. note::
           Recursion makes adjacent ``not`` operators associate from the
           outside inward before comparison parsing begins.
        """
        marker = self.stream.match(TokenKind.KW_NOT)
        if marker is None:
            return self._comparison()
        operand = self._not()
        return LclUnary(
            UnaryOperator.NOT,
            operand,
            span=_merge_span(marker.span, operand.span),
        )

    def _comparison(self) -> LclAstNode:
        """Parse an arithmetic operand followed by comparison operators.

        :returns: Comparison-chain AST node, or the arithmetic operand when no
           comparison operator is present.

        .. note::
           Operators and comparator expressions remain parallel tuples so
           chained comparisons retain their original order.
        """
        left = self.parse_arithmetic()
        operators: list[ComparisonOperator] = []
        comparators: list[LclAstNode] = []
        while (operator := self._comparison_operator()) is not None:
            operators.append(operator)
            comparators.append(self.parse_arithmetic())
        if not operators:
            return left
        return LclCompare(
            left,
            tuple(operators),
            tuple(comparators),
            span=_merge_span(left.span, comparators[-1].span),
        )

    def _comparison_operator(self) -> ComparisonOperator | None:
        """Consume one supported comparison operator from lookahead.

        :returns: Semantic comparison operator, or ``None`` without consuming
           a token when lookahead is not comparative syntax.

        .. note::
           Multi-token ``not in`` and ``is not`` operators are consumed as one
           semantic operator.
        """
        kind = self.stream.current.kind
        if kind in _SINGLE_COMPARISONS:
            self.stream.advance()
            return _SINGLE_COMPARISONS[kind]
        if kind is TokenKind.KW_NOT and self.stream.peek(1).kind is TokenKind.KW_IN:
            self.stream.advance()
            self.stream.advance()
            return ComparisonOperator.NOT_IN
        if kind is TokenKind.KW_IS:
            self.stream.advance()
            if self.stream.match(TokenKind.KW_NOT) is not None:
                return ComparisonOperator.IS_NOT
            return ComparisonOperator.IS
        return None


def parse_logical(
    stream: TokenStream,
    parse_arithmetic: Callable[[], LclAstNode],
    *,
    allow_conditional: bool = True,
) -> LclAstNode:
    """Parse the complete low-precedence expression layer.

    :param stream: Token stream positioned at the first operand.
    :param parse_arithmetic: Callback parsing one tighter arithmetic expression.
    :param allow_conditional: Parse trailing ``if``/``else`` syntax when true.
    :returns: Comparison, Boolean, coalescing, conditional, or unchanged operand.
    :raises LclSyntaxError: If an operator lacks its required operand or branch.

    .. note::
       The callback must stop before all logical-layer token kinds.
    """
    return _LogicalParser(
        stream,
        parse_arithmetic,
        allow_conditional=allow_conditional,
    ).parse()


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one logical expression.

    :param first: Span at the first operand or unary marker.
    :param last: Span at the final operand or branch.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and all intervening logical
       operators are included in the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
