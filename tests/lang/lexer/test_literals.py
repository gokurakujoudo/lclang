"""Unit tests mirroring :mod:`lclang.lang.lexer.literals`."""

import pytest

from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind, scan_tokens
from lclang.lang.lexer.literals import LiteralMatch, scan_literal


@pytest.mark.parametrize(
    ("source", "kind", "value"),
    [
        ("1_000", TokenKind.INTEGER, 1000),
        ("0b_101", TokenKind.INTEGER, 5),
        ("0o17", TokenKind.INTEGER, 15),
        ("0x_FF", TokenKind.INTEGER, 255),
        ("1.25", TokenKind.FLOAT, 1.25),
        (".5", TokenKind.FLOAT, 0.5),
        ("2e3", TokenKind.FLOAT, 2000.0),
    ],
)
def test_scans_numeric_values(source: str, kind: TokenKind, value: object) -> None:
    """Numeric matches carry converted values and exact boundaries."""
    match = scan_literal(source + " ", 0)
    assert match == LiteralMatch(kind, source, value, len(source))


@pytest.mark.parametrize(
    ("source", "value"),
    [
        (r"'line\n\t\\\x41\101'", "line\n\t\\AA"),
        (r"'\u03b1\U0001f600'", "α😀"),
        (r"'\N{LATIN SMALL LETTER A}'", "a"),
        (r"r'raw\n'", r"raw\n"),
        ('"plain"', "plain"),
        ("'''first\nsecond'''", "first\nsecond"),
    ],
)
def test_scans_text_literals(source: str, value: str) -> None:
    """Text quotes, raw content, escapes, and triples decode deterministically."""
    match = scan_literal(source, 0)
    assert match is not None
    assert match.kind is TokenKind.STRING
    assert match.value == value
    assert match.end == len(source)


@pytest.mark.parametrize(
    ("source", "value"),
    [
        (r"b'A\n\x42\101'", b"A\nBA"),
        (r"Br'raw\n'", b"raw\\n"),
    ],
)
def test_scans_bytes_literals(source: str, value: bytes) -> None:
    """Bytes prefixes and escapes produce bytes rather than text."""
    match = scan_literal(source, 0)
    assert match is not None
    assert match.kind is TokenKind.BYTES
    assert match.value == value


def test_non_literal_start_returns_none() -> None:
    """Literal matching composes with identifier and operator scanning."""
    assert scan_literal("name", 0) is None
    assert scan_literal("", 0) is None


def test_numeric_candidate_stops_before_arithmetic_operator() -> None:
    """A sign belongs to a number only immediately after an exponent marker."""
    tokens = scan_tokens("1+2")
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.INTEGER, 1),
        (TokenKind.PLUS, None),
        (TokenKind.INTEGER, 2),
        (TokenKind.EOF, None),
    ]


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("'a\\\nb'", "ab"),
        ("'a\\\r\nb'", "ab"),
    ],
)
def test_escaped_physical_newline_is_removed(source: str, value: str) -> None:
    """Both newline encodings support explicit string continuation."""
    token = scan_tokens(source)[0]
    assert token.value == value


def test_triple_literal_advances_scanner_across_crlf() -> None:
    """A multiline literal updates the following token's logical position."""
    tokens = scan_tokens("'''a\r\nb''' name")
    assert tokens[1].span.start.line == 2
    assert tokens[1].span.start.column == 6


def test_adjacent_literals_remain_separate_tokens() -> None:
    """The parser, not the scanner, owns adjacent-literal concatenation."""
    tokens = scan_tokens("'a'  'b'")
    assert [(token.kind, token.value) for token in tokens] == [
        (TokenKind.STRING, "a"),
        (TokenKind.STRING, "b"),
        (TokenKind.EOF, None),
    ]


@pytest.mark.parametrize(
    "source",
    [
        "0x",
        "1__0",
        "'unterminated",
        "'line\nbreak'",
        r"'\q'",
        r"'\x0'",
        r"b'\u0041'",
        r"b'\N{LATIN SMALL LETTER A}'",
        r"b'\777'",
        r"'\UFFFFFFFF'",
        r"'\Nbad'",
        r"'\N{LATIN SMALL LETTER A'",
        r"'\N{NOT A UNICODE NAME}'",
        "b'" + chr(256) + "'",
    ],
)
def test_invalid_literal_becomes_source_aware_syntax_error(source: str) -> None:
    """Malformed or deferred literal forms fail through the public hierarchy."""
    with pytest.raises(LclSyntaxError) as caught:
        scan_tokens(source)
    assert caught.value.span is not None
    assert caught.value.span.start.offset == 0
    assert caught.value.span.end.offset > 0
