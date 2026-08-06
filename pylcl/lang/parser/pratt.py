"""Binding-power parser for unary and binary LCL expressions."""

from __future__ import annotations

from pylcl.ast import LclAstNode, LclBinary, LclTuple, LclUnary
from pylcl.ast.operators import BinaryOperator, UnaryOperator
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind, scan_tokens
from pylcl.lang.parser.atoms import parse_atom
from pylcl.lang.parser.control_forms import parse_control_form
from pylcl.lang.parser.forms import parse_form
from pylcl.lang.parser.logical import parse_logical
from pylcl.lang.parser.primaries import parse_primaries
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceOrigin, SourceSpan
from pylcl.version import LCL_V1, LanguageVersion

_BINARY: dict[TokenKind, tuple[BinaryOperator, int, int]] = {
    TokenKind.PIPE: (BinaryOperator.BIT_OR, 10, 11),
    TokenKind.CARET: (BinaryOperator.BIT_XOR, 20, 21),
    TokenKind.AMPERSAND: (BinaryOperator.BIT_AND, 30, 31),
    TokenKind.LEFT_SHIFT: (BinaryOperator.LEFT_SHIFT, 40, 41),
    TokenKind.RIGHT_SHIFT: (BinaryOperator.RIGHT_SHIFT, 40, 41),
    TokenKind.PLUS: (BinaryOperator.ADD, 50, 51),
    TokenKind.MINUS: (BinaryOperator.SUBTRACT, 50, 51),
    TokenKind.STAR: (BinaryOperator.MULTIPLY, 60, 61),
    TokenKind.AT: (BinaryOperator.MATRIX_MULTIPLY, 60, 61),
    TokenKind.SLASH: (BinaryOperator.TRUE_DIVIDE, 60, 61),
    TokenKind.DOUBLE_SLASH: (BinaryOperator.FLOOR_DIVIDE, 60, 61),
    TokenKind.PERCENT: (BinaryOperator.MODULO, 60, 61),
    TokenKind.DOUBLE_STAR: (BinaryOperator.POWER, 80, 80),
}
_UNARY = {
    TokenKind.PLUS: UnaryOperator.POSITIVE,
    TokenKind.MINUS: UnaryOperator.NEGATIVE,
    TokenKind.TILDE: UnaryOperator.INVERT,
}


class _PrattParser:
    """Coordinate recursive-descent forms with binding-power parsing.

    .. note::
       The parser owns one token stream and passes its methods as callbacks so
       nested forms share the same precedence and delimiter state.
    """

    def __init__(self, stream: TokenStream) -> None:
        """Bind the token stream used by the expression parser.

        :param stream: Token stream containing the expression and EOF marker.
        :returns: ``None``.

        .. note::
           The stream is consumed in place by all nested parser callbacks.
        """
        self.stream = stream

    def parse(self) -> LclAstNode:
        """Parse one complete expression and reject trailing input.

        :returns: Immutable AST root, including a tuple node for top-level
           comma-separated expressions.
        :raises LclSyntaxError: If input remains after the parsed expression.

        .. note::
           Top-level commas are handled after complete-expression parsing so
           each tuple element may contain any supported form.
        """
        node = self._parse_complete()
        if self.stream.match(TokenKind.COMMA) is not None:
            elements = [node]
            while self.stream.current.kind is not TokenKind.EOF:
                elements.append(self._parse_complete())
                if self.stream.match(TokenKind.COMMA) is None:
                    break
            node = LclTuple(
                tuple(elements),
                span=_merge_span(elements[0].span, elements[-1].span),
            )
        if self.stream.current.kind is not TokenKind.EOF:
            raise LclSyntaxError("unexpected trailing token", span=self.stream.current.span)
        return node

    def _parse_complete(self) -> LclAstNode:
        """Parse control forms, ordinary forms, or logical expressions.

        :returns: Complete-expression AST node at the current stream position.

        .. note::
           Control and function-like forms are tried before logical parsing so
           their keywords remain available to the dedicated form parsers.
        """
        control = parse_control_form(
            self.stream,
            self._parse_complete,
            self._parse_nonconditional,
        )
        if control is not None:
            return control
        form = parse_form(
            self.stream,
            self._parse_complete,
            self._parse_nonconditional,
        )
        if form is not None:
            return form
        return parse_logical(self.stream, lambda: self._parse_bp(0))

    def _parse_nonconditional(self) -> LclAstNode:
        """Parse a logical expression while excluding conditional syntax.

        :returns: Nonconditional logical or arithmetic AST node.

        .. note::
           This boundary is used by defaults, matchers, and comprehension
           clauses that must leave a trailing conditional token to their owner.
        """
        return parse_logical(
            self.stream,
            lambda: self._parse_bp(0),
            allow_conditional=False,
        )

    def _parse_bp(self, minimum: int) -> LclAstNode:
        """Parse unary and binary expressions at a binding-power threshold.

        :param minimum: Lowest left binding power accepted at this recursion
           level.
        :returns: AST node for the parsed unary, primary, or binary expression.

        .. note::
           Right binding powers determine associativity, while unary operands
           recurse at the language's fixed unary precedence.
        """
        token = self.stream.current
        left: LclAstNode
        if token.kind in _UNARY:
            self.stream.advance()
            operand = self._parse_bp(70)
            left = LclUnary(
                operator=_UNARY[token.kind],
                operand=operand,
                span=_merge_span(token.span, operand.span),
            )
        else:
            left = parse_atom(
                self.stream,
                self._parse_complete,
                self._parse_nonconditional,
            )
            left = parse_primaries(self.stream, left, self._parse_complete)
        while self.stream.current.kind in _BINARY:
            operator, left_bp, right_bp = _BINARY[self.stream.current.kind]
            if left_bp < minimum:
                break
            self.stream.advance()
            right = self._parse_bp(right_bp)
            left = LclBinary(
                left=left,
                operator=operator,
                right=right,
                span=_merge_span(left.span, right.span),
            )
        return left


def parse_expression(
    text: str,
    *,
    origin: SourceOrigin | None = None,
    version: LanguageVersion = LCL_V1,
) -> LclAstNode:
    """Parse one complete LCL expression using the selected grammar version.

    :param text: Complete expression source.
    :param origin: Optional diagnostic source origin.
    :param version: Independent LCL grammar version.
    :returns: Immutable custom AST root spanning the parsed expression.
    :raises ValueError: If *version* is unsupported.
    :raises LclSyntaxError: If *text* is empty, malformed, or has trailing input.

    .. note::
       Physical newline tokens are separators; no Python AST or execution is used.
    """
    if version is not LCL_V1:
        raise ValueError(f"unsupported LCL language version: {version}")
    stream = TokenStream(scan_tokens(text, origin=origin))
    return _PrattParser(stream).parse()


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one parsed expression.

    :param first: Span at the first token or operand.
    :param last: Span at the final token or operand.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and all intervening
       operators or nested syntax are covered by the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
