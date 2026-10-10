"""Convert lexical interpolated strings into semantic AST nodes.

Defines ``internal_parse_fstring``, ``internal_convert_value``, ``internal_convert_part``,
``internal_parse_field_expression``.
"""

from __future__ import annotations

from typing import cast

from lclang.common.source_location import SourceSpan, advance_source_position
from lclang.error import LanguageErrorCode, LclSyntaxError
from lclang.lang.ast import (
    LclAstNode,
    LclFormattedValue,
    LclJoinedString,
    LclStringText,
)
from lclang.lang.engine.lexer import Token, scan_tokens
from lclang.lang.engine.lexer.fstring_parts import FStringField, FStringText, FStringValue


def internal_parse_fstring(token: Token) -> LclJoinedString:
    """Convert one lexical f-string token into a joined-string node.

    :param token: F-string token containing its lexical value and source span.
    :returns: Semantic joined-string AST node.

    .. note::
       The lexical payload is cast to its f-string value type because token
       classification guarantees that shape before this helper is called.
    """
    value = cast(FStringValue, token.value)
    return internal_convert_value(value, token.span)


def internal_convert_value(value: FStringValue, span: SourceSpan) -> LclJoinedString:
    """Convert all lexical f-string parts into semantic AST values.

    :param value: Lexical f-string value containing text and field parts.
    :param span: Source span assigned to the resulting semantic nodes.
    :returns: Joined-string AST node preserving part order.

    .. note::
       Nested format specifications recurse through this same conversion path
       so their fields receive the same semantic treatment.
    """
    return LclJoinedString(
        values=tuple(internal_convert_part(part, span) for part in value.parts),
        span=span,
    )


def internal_convert_part(
    part: FStringText | FStringField,
    span: SourceSpan,
) -> LclAstNode:
    """Convert one lexical text or replacement-field part.

    :param part: Lexical text segment or replacement field.
    :param span: Source span attached to the semantic part.
    :returns: String-text or formatted-value AST node.
    :raises LclSyntaxError: If the replacement field expression is invalid.

    .. note::
       Field conversion, format specifications, debug markers, and explicit
       conversions are preserved in the formatted-value node.
    """
    if isinstance(part, FStringText):
        return LclStringText(text=part.text, span=span)
    expression_span = span
    if part.expression_offset is not None and span.snapshot is not None:
        offset = span.start.offset - span.snapshot.start.offset
        original = span.snapshot.text[offset : span.end.offset - span.snapshot.start.offset]
        quote_at = next((index for index, char in enumerate(original) if char in "'\""), 0)
        start = advance_source_position(span.start, original[: quote_at + part.expression_offset])
        expression_span = SourceSpan(
            span.origin,
            start,
            advance_source_position(start, part.expression),
            snapshot=span.snapshot,
        )
    try:
        expression = internal_parse_field_expression(part.expression, expression_span)
    except LclSyntaxError as error:
        raise LclSyntaxError(error.message, span=span, code=error.code) from error
    format_spec = (
        None if part.format_spec is None else internal_convert_value(part.format_spec, span)
    )
    return LclFormattedValue(
        expression=expression,
        conversion=part.conversion,
        format_spec=format_spec,
        debug=part.debug,
        span=span,
    )


def internal_parse_field_expression(source: str, span: SourceSpan) -> LclAstNode:
    """Parse the expression contained by one f-string replacement field.

    :param source: Expression source extracted from the replacement field.
    :param span: Source span used for the translated syntax diagnostic.
    :returns: Semantic AST root for the field expression.
    :raises LclSyntaxError: If the field expression cannot be parsed.

    .. note::
       Nested parser errors are reissued with an f-string-specific message and
       the enclosing f-string span so callers receive one consistent location.
    """
    from lclang.lang.engine.parser.pratt_parser import parse_tokens

    try:
        return parse_tokens(
            scan_tokens(source, origin=span.origin, start=span.start, snapshot=span.snapshot)
        )
    except LclSyntaxError as error:
        message = f"invalid f-string expression: {error.message}"
        raise LclSyntaxError(
            message, span=span, code=LanguageErrorCode.E26_PARSE_FIELD_EXPRESSION_FAILURE
        ) from error
