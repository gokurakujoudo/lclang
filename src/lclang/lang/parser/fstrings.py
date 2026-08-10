"""Convert lexical interpolated strings into semantic AST nodes."""

from __future__ import annotations

from typing import cast

from lclang.ast import (
    LclAstNode,
    LclFormattedValue,
    LclJoinedString,
    LclStringText,
)
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import Token
from lclang.lang.lexer.fstring_values import FStringField, FStringText, FStringValue
from lclang.source import SourceSpan


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

    .. note::
       Field conversion, format specifications, debug markers, and explicit
       conversions are preserved in the formatted-value node.
    """
    if isinstance(part, FStringText):
        return LclStringText(text=part.text, span=span)
    expression = internal_parse_field_expression(part.expression, span)
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
    from lclang.lang.parser.pratt import parse_expression

    try:
        return parse_expression(source, origin=span.origin)
    except LclSyntaxError as error:
        message = f"invalid f-string expression: {error.message}"
        raise LclSyntaxError(message, span=span) from error
