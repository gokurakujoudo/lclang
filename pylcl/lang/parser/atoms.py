"""Atom, grouping, and adjacent-literal parsing."""

from __future__ import annotations

from collections.abc import Callable

from pylcl.ast import LclAstNode, LclConstant, LclName
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind
from pylcl.lang.parser.displays import parse_display
from pylcl.lang.parser.fstrings import _parse_fstring
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceSpan
from pylcl.types import VarName

_LITERALS = {
    TokenKind.INTEGER,
    TokenKind.FLOAT,
    TokenKind.STRING,
    TokenKind.BYTES,
}
_CONSTANT_KEYWORDS = {
    TokenKind.KW_TRUE: True,
    TokenKind.KW_FALSE: False,
    TokenKind.KW_NONE: None,
}


def parse_atom(
    stream: TokenStream,
    parse_nested: Callable[[], LclAstNode],
    parse_nonconditional: Callable[[], LclAstNode] | None = None,
) -> LclAstNode:
    """Parse one atomic or parenthesized expression.

    :param stream: Token stream positioned at the candidate atom.
    :param parse_nested: Callback parsing content after an opening parenthesis.
    :param parse_nonconditional: Optional callback for comprehension clauses.
    :returns: Immutable atom or grouped expression node.
    :raises LclSyntaxError: If lookahead cannot begin a supported atom.

    .. note::
       Tuple displays are delegated while f-strings become semantic AST nodes.
    """
    token = stream.current
    if token.kind in _LITERALS:
        return _parse_literal(stream)
    if token.kind in _CONSTANT_KEYWORDS:
        stream.advance()
        return LclConstant(value=_CONSTANT_KEYWORDS[token.kind], span=token.span)
    if token.kind is TokenKind.IDENTIFIER:
        stream.advance()
        return LclName(identifier=VarName(token.lexeme), span=token.span)
    if token.kind in {TokenKind.LPAREN, TokenKind.LBRACKET, TokenKind.LBRACE}:
        clause_parser = parse_nested if parse_nonconditional is None else parse_nonconditional
        return parse_display(stream, parse_nested, clause_parser)
    if token.kind is TokenKind.FSTRING:
        stream.advance()
        return _parse_fstring(token)
    raise LclSyntaxError("expected an expression atom", span=token.span)


def _parse_literal(stream: TokenStream) -> LclConstant:
    """Parse one literal and merge compatible adjacent text literals.

    :param stream: Token stream positioned at the first literal token.
    :returns: Constant node containing the decoded literal value.
    :raises LclSyntaxError: If adjacent text and bytes literals are mixed.

    .. note::
       Only adjacent literals of the same string/bytes kind are merged; other
       literal kinds consume exactly one token.
    """
    first = stream.advance()
    value = first.value
    last = first
    if first.kind in {TokenKind.STRING, TokenKind.BYTES}:
        while stream.current.kind is first.kind:
            last = stream.advance()
            value = value + last.value  # type: ignore[operator]
        opposite = TokenKind.BYTES if first.kind is TokenKind.STRING else TokenKind.STRING
        if stream.current.kind is opposite:
            raise LclSyntaxError(
                "cannot mix adjacent text and bytes literals",
                span=stream.current.span,
            )
    return LclConstant(value=value, span=_merge_span(first.span, last.span))


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join two spans that belong to one syntactic literal expression.

    :param first: Span of the first consumed literal token.
    :param last: Span of the final consumed adjacent literal token.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The first span supplies the shared source origin, while intervening
       source text is intentionally covered by the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
