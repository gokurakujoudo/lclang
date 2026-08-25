"""Binding-power parser for unary and binary LCL expressions."""

from __future__ import annotations

from lclang.ast import LclAstNode, LclBinary, LclTuple, LclUnary
from lclang.ast.operators import BinaryOperator, UnaryOperator
from lclang.diagnostics import (
    internal_render_value,
    internal_trace,
    internal_verbose_enabled,
)
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import Token, TokenKind, scan_tokens
from lclang.lang.parser.atoms import parse_atom
from lclang.lang.parser.control_forms import parse_control_form
from lclang.lang.parser.forms import parse_form
from lclang.lang.parser.logical import parse_logical
from lclang.lang.parser.primaries import parse_primaries
from lclang.lang.parser.stream import TokenStream
from lclang.lang.printer import to_source
from lclang.scopes import is_frame_proxy
from lclang.source import SourceOrigin, SourceSpan
from lclang.version import LCL_V1, LanguageVersion

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


class InternalPrattParser:
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
        node = self.internal_parse_complete()
        if self.stream.match(TokenKind.COMMA) is not None:
            elements = [node]
            while self.stream.current.kind is not TokenKind.EOF:
                elements.append(self.internal_parse_complete())
                if self.stream.match(TokenKind.COMMA) is None:
                    break
            node = LclTuple(
                tuple(elements),
                span=internal_merge_span(elements[0].span, elements[-1].span),
            )
        if self.stream.current.kind is not TokenKind.EOF:
            raise LclSyntaxError("unexpected trailing token", span=self.stream.current.span)
        return node

    def internal_parse_complete(self) -> LclAstNode:
        """Parse control forms, ordinary forms, or logical expressions.

        :returns: Complete-expression AST node at the current stream position.

        .. note::
           Control and function-like forms are tried before logical parsing so
           their keywords remain available to the dedicated form parsers.
        """
        control = parse_control_form(
            self.stream,
            self.internal_parse_complete,
            self.internal_parse_nonconditional,
        )
        if control is not None:
            return control
        form = parse_form(
            self.stream,
            self.internal_parse_complete,
            self.internal_parse_nonconditional,
        )
        if form is not None:
            return form
        return parse_logical(self.stream, lambda: self.internal_parse_bp(0))

    def internal_parse_nonconditional(self) -> LclAstNode:
        """Parse a logical expression while excluding conditional syntax.

        :returns: Nonconditional logical or arithmetic AST node.

        .. note::
           This boundary is used by defaults, matchers, and comprehension
           clauses that must leave a trailing conditional token to their owner.
        """
        return parse_logical(
            self.stream,
            lambda: self.internal_parse_bp(0),
            allow_conditional=False,
        )

    def internal_parse_bp(self, minimum: int) -> LclAstNode:
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
            operand = self.internal_parse_bp(70)
            left = LclUnary(
                operator=_UNARY[token.kind],
                operand=operand,
                span=internal_merge_span(token.span, operand.span),
            )
        else:
            left = parse_atom(
                self.stream,
                self.internal_parse_complete,
                self.internal_parse_nonconditional,
            )
            left = parse_primaries(self.stream, left, self.internal_parse_complete)
        while self.stream.current.kind in _BINARY:
            operator, left_bp, right_bp = _BINARY[self.stream.current.kind]
            if left_bp < minimum:
                break
            self.stream.advance()
            right = self.internal_parse_bp(right_bp)
            left = LclBinary(
                left=left,
                operator=operator,
                right=right,
                span=internal_merge_span(left.span, right.span),
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
    try:
        node = parse_tokens(scan_tokens(text, origin=origin), version=version)
    except BaseException as error:
        if internal_verbose_enabled():
            origin_name = "<string>" if origin is None else str(origin.name)
            internal_trace(
                "parse",
                f"origin={origin_name!r} expression={internal_render_value(text)} "
                f"error={internal_render_value(error)}",
            )
        raise
    if internal_verbose_enabled():
        internal_trace(
            "parse",
            f"origin={str(node.span.origin.name)!r} expression={internal_render_value(text)} "
            f"ast={internal_render_value(node, lambda: to_source(node))}",
        )
    return node


def parse_tokens(
    tokens: list[Token],
    *,
    version: LanguageVersion = LCL_V1,
) -> LclAstNode:
    """Parse one complete pre-scanned LCL token sequence.

    :param tokens: Source-aware tokens ending with EOF.
    :param version: Independent LCL grammar version.
    :returns: Immutable custom AST root.
    :raises ValueError: If *version* is unsupported or tokens omit EOF.
    :raises LclSyntaxError: If the token sequence is malformed.

    .. note::
       Configuration parsing uses this boundary to replace magic identifiers
       with literal tokens without changing the standalone expression API.
    """
    if version is not LCL_V1:
        raise ValueError(f"unsupported LCL language version: {version}")
    node = InternalPrattParser(TokenStream(tokens)).parse()
    markers = tuple(item for item in node.walk() if is_frame_proxy(item))
    if markers and not is_frame_proxy(node):
        raise LclSyntaxError(
            "FRAME_PROXY must be a complete expression",
            span=markers[0].span,
        )
    return node


def internal_merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one parsed expression.

    :param first: Span at the first token or operand.
    :param last: Span at the final token or operand.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and all intervening
       operators or nested syntax are covered by the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
