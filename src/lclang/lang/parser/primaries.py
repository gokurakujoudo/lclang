"""Postfix parsing for attributes, subscriptions, slices, and calls."""

from __future__ import annotations

from collections.abc import Callable

from lclang.ast import (
    LclAstNode,
    LclAttribute,
    LclCall,
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclName,
    LclPositionalArgument,
    LclSafeAttribute,
    LclSlice,
    LclStarArgument,
    LclSubscript,
    LclTuple,
)
from lclang.ast.call_arguments import LclCallArgument
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind
from lclang.lang.parser.stream import TokenStream
from lclang.source import SourceSpan, merge_source_spans
from lclang.types import VarName


class InternalPrimaryParser:
    """Parse left-associated postfix operations after an initial expression.

    .. note::
       The parser owns no token data; it advances the supplied stream and
       delegates nested expressions to the callback captured at construction.
    """

    def __init__(self, stream: TokenStream, parse_nested: Callable[[], LclAstNode]) -> None:
        """Create a postfix parser over one token stream.

        :param stream: Token stream positioned after the initial expression.
        :param parse_nested: Callback parsing nested index and argument values.
        :returns: ``None``.

        .. note::
           The callback is retained so nested expressions use the enclosing
           Pratt parser's current precedence rules.
        """
        self.stream = stream
        self.parse_nested = parse_nested

    def parse(self, value: LclAstNode) -> LclAstNode:
        """Consume every contiguous postfix operation after *value*.

        :param value: Already-parsed receiver expression.
        :returns: Final left-associated primary chain.
        :raises LclSyntaxError: If a postfix form is incomplete or invalid.

        .. note::
           Parsing stops at the first token that cannot begin an attribute,
           subscript, or call, leaving that token for the enclosing parser.
        """
        while self.stream.current.kind in {
            TokenKind.DOT,
            TokenKind.QUESTION_DOT,
            TokenKind.LBRACKET,
            TokenKind.LPAREN,
        }:
            kind = self.stream.current.kind
            if kind in {TokenKind.DOT, TokenKind.QUESTION_DOT}:
                value = self.internal_attribute(value, safe=kind is TokenKind.QUESTION_DOT)
            elif kind is TokenKind.LBRACKET:
                value = self.internal_subscript(value)
            else:
                value = self.internal_call(value)
        return value

    def internal_attribute(self, value: LclAstNode, *, safe: bool) -> LclAstNode:
        """Parse a direct or null-propagating attribute access.

        :param value: Receiver expression preceding the attribute operator.
        :param safe: Whether the operator is the null-propagating form.
        :returns: Attribute AST node spanning the receiver and its name.
        :raises LclSyntaxError: If the attribute name is missing.

        .. note::
           Safe access is represented by a distinct AST node so evaluation can
           preserve its short-circuiting semantics.
        """
        self.stream.advance()
        name = self.stream.expect(TokenKind.IDENTIFIER, "expected attribute name")
        span = merge_source_spans(value.span, name.span)
        node_type = LclSafeAttribute if safe else LclAttribute
        return node_type(value=value, name=VarName(name.lexeme), span=span)

    def internal_subscript(self, value: LclAstNode) -> LclSubscript:
        """Parse an index, tuple index, or slice subscription.

        :param value: Receiver expression preceding the opening bracket.
        :returns: Subscript AST node containing the parsed index expression.
        :raises LclSyntaxError: If the bracketed expression is empty or lacks
           its closing bracket.

        .. note::
           Comma-separated indices become one tuple node, matching the
           language's distinction between tuple and slice subscripts.
        """
        opening = self.stream.advance()
        index: LclAstNode
        if self.stream.current.kind is TokenKind.RBRACKET:
            raise LclSyntaxError("subscript cannot be empty", span=self.stream.current.span)
        if self.stream.match(TokenKind.COLON) is not None:
            index = self.internal_slice(opening.span, None)
        else:
            first = self.parse_nested()
            if self.stream.match(TokenKind.COLON) is not None:
                index = self.internal_slice(opening.span, first)
            elif self.stream.match(TokenKind.COMMA) is not None:
                elements = [first]
                while self.stream.peek().kind is not TokenKind.RBRACKET:
                    elements.append(self.parse_nested())
                    if self.stream.match(TokenKind.COMMA) is None:
                        break
                closing = self.stream.expect(TokenKind.RBRACKET, "expected closing bracket")
                index = LclTuple(
                    tuple(elements),
                    span=merge_source_spans(opening.span, closing.span),
                )
            else:
                closing = self.stream.expect(TokenKind.RBRACKET, "expected closing bracket")
                return LclSubscript(
                    value=value,
                    index=first,
                    span=merge_source_spans(value.span, closing.span),
                )
        return LclSubscript(
            value=value,
            index=index,
            span=merge_source_spans(value.span, index.span),
        )

    def internal_slice(self, opening: SourceSpan, lower: LclAstNode | None) -> LclSlice:
        """Parse the upper and optional step parts of a slice.

        :param opening: Span of the opening bracket for the subscription.
        :param lower: Optional expression before the first slice colon.
        :returns: Slice AST node with lower, upper, and step expressions.
        :raises LclSyntaxError: If the slice has no closing bracket.

        .. note::
           Missing upper or step expressions remain ``None`` and are not
           synthesized as literal values.
        """
        upper = None
        if self.stream.current.kind not in {TokenKind.COLON, TokenKind.RBRACKET}:
            upper = self.parse_nested()
        step = None
        has_step = self.stream.match(TokenKind.COLON) is not None
        if has_step and self.stream.current.kind is not TokenKind.RBRACKET:
            step = self.parse_nested()
        closing = self.stream.expect(TokenKind.RBRACKET, "expected closing bracket after slice")
        return LclSlice(
            lower=lower,
            upper=upper,
            step=step,
            span=merge_source_spans(opening, closing.span),
        )

    def internal_call(self, function: LclAstNode) -> LclCall:
        """Parse a call argument list following a callable expression.

        :param function: Expression supplying the callable receiver.
        :returns: Call AST node containing arguments in source order.
        :raises LclSyntaxError: If an argument or closing parenthesis is
           invalid or incomplete.

        .. note::
           The method tracks keyword ordering and unpacking while delegating
           individual argument forms to :meth:`_argument`.
        """
        self.stream.advance()
        arguments: list[LclCallArgument] = []
        explicit_names: set[str] = set()
        seen_keyword = False
        seen_keyword_unpack = False
        if self.stream.current.kind is not TokenKind.RPAREN:
            while True:
                argument = self.internal_argument(
                    seen_keyword=seen_keyword,
                    seen_keyword_unpack=seen_keyword_unpack,
                    explicit_names=explicit_names,
                )
                arguments.append(argument)
                seen_keyword |= isinstance(argument, LclKeywordArgument)
                seen_keyword_unpack |= isinstance(argument, LclKeywordUnpackArgument)
                if self.stream.match(TokenKind.COMMA) is None:
                    break
                if self.stream.peek().kind is TokenKind.RPAREN:
                    break
        closing = self.stream.expect(TokenKind.RPAREN, "expected closing call parenthesis")
        return LclCall(
            function=function,
            arguments=tuple(arguments),
            span=merge_source_spans(function.span, closing.span),
        )

    def internal_argument(
        self,
        *,
        seen_keyword: bool,
        seen_keyword_unpack: bool,
        explicit_names: set[str],
    ) -> LclCallArgument:
        """Parse one positional, keyword, or unpacked call argument.

        :param seen_keyword: Whether a regular keyword argument was parsed.
        :param seen_keyword_unpack: Whether a keyword-unpacking argument was
           parsed.
        :param explicit_names: Mutable set of already-used keyword names.
        :returns: Normalized call-argument AST node.
        :raises LclSyntaxError: If argument ordering, unpacking, or keyword
           syntax violates the call grammar.

        .. note::
           The keyword-name set is updated in place so duplicate detection
           covers the complete argument list.
        """
        marker = self.stream.match(TokenKind.DOUBLE_STAR)
        if marker is not None:
            value = self.parse_nested()
            return LclKeywordUnpackArgument(
                value,
                span=merge_source_spans(marker.span, value.span),
            )
        marker = self.stream.match(TokenKind.STAR)
        if marker is not None:
            if seen_keyword_unpack:
                raise LclSyntaxError(
                    "star argument cannot follow keyword unpacking",
                    span=marker.span,
                )
            value = self.parse_nested()
            return LclStarArgument(value, span=merge_source_spans(marker.span, value.span))
        candidate = self.parse_nested()
        if self.stream.match(TokenKind.EQUAL) is not None:
            if not isinstance(candidate, LclName):
                raise LclSyntaxError("keyword target must be a name", span=candidate.span)
            if candidate.identifier in explicit_names:
                raise LclSyntaxError("duplicate keyword argument", span=candidate.span)
            explicit_names.add(candidate.identifier)
            value = self.parse_nested()
            return LclKeywordArgument(
                candidate.identifier,
                value,
                span=merge_source_spans(candidate.span, value.span),
            )
        if seen_keyword or seen_keyword_unpack:
            raise LclSyntaxError(
                "positional argument follows keyword argument",
                span=candidate.span,
            )
        return LclPositionalArgument(candidate, span=candidate.span)


def parse_primaries(
    stream: TokenStream,
    value: LclAstNode,
    parse_nested: Callable[[], LclAstNode],
) -> LclAstNode:
    """Extend *value* through every immediately following postfix operation.

    :param stream: Token stream positioned after the initial value.
    :param value: Already-parsed receiver expression.
    :param parse_nested: Callback parsing nested index and argument expressions.
    :returns: Final left-associated primary chain.
    :raises LclSyntaxError: If a postfix form is incomplete or invalid.

    .. note::
       The callback stops naturally at postfix delimiters and commas.
    """
    return InternalPrimaryParser(stream, parse_nested).parse(value)
