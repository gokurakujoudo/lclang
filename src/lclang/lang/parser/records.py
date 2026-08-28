"""Parsing for immutable named record displays."""

from __future__ import annotations

from collections.abc import Callable

from lclang.ast import LclAstNode, LclRecordDisplay, LclRecordField
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind
from lclang.lang.parser.bindings import validate_binding_name
from lclang.lang.parser.stream import TokenStream
from lclang.source import SourceSpan
from lclang.types import VarName


def parse_record(
    stream: TokenStream,
    opening: SourceSpan,
    parse_nested: Callable[[], LclAstNode],
) -> LclRecordDisplay:
    """Parse a non-empty comma-separated record after its opening brace.

    :param stream: Token stream positioned at the first field name.
    :param opening: Span of the already-consumed opening brace.
    :param parse_nested: Callback parsing each complete field expression.
    :returns: Immutable record-display node covering both braces.
    :raises LclSyntaxError: If a name repeats or record syntax is malformed.
    """
    fields: list[LclRecordField] = []
    names: set[str] = set()
    while True:
        name = stream.expect(TokenKind.IDENTIFIER, "expected record field name")
        validate_binding_name(name)
        if name.lexeme in names:
            raise LclSyntaxError("duplicate record field", span=name.span)
        names.add(name.lexeme)
        stream.expect(TokenKind.EQUAL, "expected equals after record field name")
        value = parse_nested()
        fields.append(
            LclRecordField(
                VarName(name.lexeme),
                value,
                span=SourceSpan(name.span.origin, name.span.start, value.span.end),
            )
        )
        if stream.match(TokenKind.COMMA) is None or stream.current.kind is TokenKind.RBRACE:
            break
    closing = stream.expect(TokenKind.RBRACE, "expected closing record brace")
    return LclRecordDisplay(
        tuple(fields),
        span=SourceSpan(opening.origin, opening.start, closing.span.end),
    )
