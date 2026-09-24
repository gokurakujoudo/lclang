"""Unit tests mirroring :mod:`lclang.lang.lexer.scanner`."""

import pytest

from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind, scan_tokens
from lclang.source import SourceOrigin
from lclang.types import SourceName


def kinds(source: str) -> list[TokenKind]:
    """Return token kinds for compact scanner assertions."""
    return [token.kind for token in scan_tokens(source)]


def test_scans_identifiers_keywords_and_delimiters() -> None:
    """Core names, reserved words, punctuation, and operators are distinct."""
    source = "name True and None ( ) [ ] { } , : . + - * / % @ ~ & | ^ < > ="
    assert kinds(source) == [
        TokenKind.IDENTIFIER,
        TokenKind.KW_TRUE,
        TokenKind.KW_AND,
        TokenKind.KW_NONE,
        TokenKind.LPAREN,
        TokenKind.RPAREN,
        TokenKind.LBRACKET,
        TokenKind.RBRACKET,
        TokenKind.LBRACE,
        TokenKind.RBRACE,
        TokenKind.COMMA,
        TokenKind.COLON,
        TokenKind.DOT,
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.PERCENT,
        TokenKind.AT,
        TokenKind.TILDE,
        TokenKind.AMPERSAND,
        TokenKind.PIPE,
        TokenKind.CARET,
        TokenKind.LESS,
        TokenKind.GREATER,
        TokenKind.EQUAL,
        TokenKind.EOF,
    ]


def test_longest_operator_wins() -> None:
    """Compound operators cannot be split into valid shorter operators."""
    assert kinds("** // << >> <= >= == != ?. ?? ->") == [
        TokenKind.DOUBLE_STAR,
        TokenKind.DOUBLE_SLASH,
        TokenKind.LEFT_SHIFT,
        TokenKind.RIGHT_SHIFT,
        TokenKind.LESS_EQUAL,
        TokenKind.GREATER_EQUAL,
        TokenKind.EQUAL_EQUAL,
        TokenKind.NOT_EQUAL,
        TokenKind.QUESTION_DOT,
        TokenKind.DOUBLE_QUESTION,
        TokenKind.ARROW,
        TokenKind.EOF,
    ]


def test_all_v1_keywords_are_reserved() -> None:
    """The keyword table is explicit rather than parser-context dependent."""
    source = (
        "and or not if else for in is True False None raise try except " "finally assert with as"
    )
    assert all(token.kind is not TokenKind.IDENTIFIER for token in scan_tokens(source)[:-1])


def test_unicode_identifier_and_crlf_positions_count_code_points() -> None:
    """Coordinates use code points and a CRLF is one logical newline."""
    origin = SourceOrigin(SourceName("unicode.lcl"))
    tokens = scan_tokens("α\r\nbeta", origin=origin)
    first, newline, second, eof = tokens
    assert first.lexeme == "α"
    assert (first.span.start.line, first.span.start.column, first.span.start.offset) == (1, 1, 0)
    assert (first.span.end.line, first.span.end.column, first.span.end.offset) == (1, 2, 1)
    assert newline.kind is TokenKind.NEWLINE
    assert (newline.span.end.line, newline.span.end.column, newline.span.end.offset) == (2, 1, 3)
    assert (second.span.start.line, second.span.start.column, second.span.start.offset) == (2, 1, 3)
    assert eof.span.start == eof.span.end
    assert eof.span.origin is origin


def test_comments_and_horizontal_whitespace_are_ignored() -> None:
    """A comment is discarded while its terminating newline is preserved."""
    assert kinds("first \t\f# comment\n second") == [
        TokenKind.IDENTIFIER,
        TokenKind.NEWLINE,
        TokenKind.IDENTIFIER,
        TokenKind.EOF,
    ]


def test_bare_carriage_return_is_a_newline() -> None:
    """Legacy line endings still advance to a single new logical line."""
    assert kinds("a\rb") == [
        TokenKind.IDENTIFIER,
        TokenKind.NEWLINE,
        TokenKind.IDENTIFIER,
        TokenKind.EOF,
    ]


def test_unsupported_character_has_a_precise_syntax_error() -> None:
    """Lexical failures identify exactly the unsupported code point."""
    with pytest.raises(LclSyntaxError) as caught:
        scan_tokens("!")
    error = caught.value
    assert error.span is not None
    assert (error.span.start.offset, error.span.end.offset) == (0, 1)
    assert "unsupported character" in error.message


def test_empty_source_has_one_zero_width_eof() -> None:
    """Even empty input produces one source-aware sentinel token."""
    tokens = scan_tokens("")
    assert len(tokens) == 1
    assert tokens[0].kind is TokenKind.EOF
    assert tokens[0].span.start == tokens[0].span.end
