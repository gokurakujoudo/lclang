"""Atom, grouping, and adjacent-literal parsing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from lclang.ast import LclAstNode, LclConstant, LclName
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind
from lclang.lang.parser.displays import parse_display
from lclang.lang.parser.fstrings import internal_parse_fstring
from lclang.lang.parser.stream import TokenStream
from lclang.scopes import FRAME_PROXY
from lclang.source import merge_source_spans
from lclang.types import VarName

# Unitless literal dispatch follows lexer token kinds; the explicit mapping preserves literal
# values and constant-keyword semantics.
_LITERALS = {
    TokenKind.INTEGER,
    TokenKind.FLOAT,
    TokenKind.STRING,
    TokenKind.BYTES,
}
# Unitless literal dispatch follows lexer token kinds; the explicit mapping preserves literal
# values and constant-keyword semantics.
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
        return internal_parse_literal(stream)
    if token.kind in _CONSTANT_KEYWORDS:
        stream.advance()
        return LclConstant(value=_CONSTANT_KEYWORDS[token.kind], span=token.span)
    if token.kind is TokenKind.IDENTIFIER:
        stream.advance()
        if token.lexeme == "FRAME_PROXY":
            return LclConstant(value=FRAME_PROXY, span=token.span)
        return LclName(identifier=VarName(token.lexeme), span=token.span)
    if token.kind in {TokenKind.LPAREN, TokenKind.LBRACKET, TokenKind.LBRACE}:
        clause_parser = parse_nested if parse_nonconditional is None else parse_nonconditional
        return parse_display(stream, parse_nested, clause_parser)
    if token.kind is TokenKind.FSTRING:
        stream.advance()
        return internal_parse_fstring(token)
    raise LclSyntaxError("expected an expression atom", span=token.span)


def internal_parse_literal(stream: TokenStream) -> LclConstant:
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
            value = cast(Any, value) + last.value
        opposite = TokenKind.BYTES if first.kind is TokenKind.STRING else TokenKind.STRING
        if stream.current.kind is opposite:
            raise LclSyntaxError(
                "cannot mix adjacent text and bytes literals",
                span=stream.current.span,
            )
    return LclConstant(value=value, span=merge_source_spans(first.span, last.span))
