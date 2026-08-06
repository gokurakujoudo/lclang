"""Unit tests mirroring :mod:`pylcl.lang.parser.stream`."""

import pytest

from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind, scan_tokens
from pylcl.lang.parser.stream import TokenStream


def test_stream_normalizes_newlines_and_supports_lookahead() -> None:
    """Parser cursor operations expose tokens without physical-newline noise."""
    stream = TokenStream(scan_tokens("name\n+ 1"))
    assert stream.current.kind is TokenKind.IDENTIFIER
    assert stream.match(TokenKind.MINUS) is None
    assert stream.advance().lexeme == "name"
    assert stream.match(TokenKind.PLUS) is not None
    current = stream.current
    assert current.kind is TokenKind.INTEGER


def test_expect_reports_current_span_without_consuming_mismatch() -> None:
    """Required-token failures preserve the unexpected token for diagnostics."""
    stream = TokenStream(scan_tokens("name"))
    with pytest.raises(LclSyntaxError) as caught:
        stream.expect(TokenKind.RPAREN, "expected closing parenthesis")
    assert caught.value.span == stream.current.span
    assert stream.current.kind is TokenKind.IDENTIFIER


def test_advancing_eof_is_stable() -> None:
    """Repeated sentinel reads cannot run beyond the token sequence."""
    stream = TokenStream(scan_tokens(""))
    assert stream.advance().kind is TokenKind.EOF
    assert stream.advance().kind is TokenKind.EOF


def test_peek_supports_bounded_non_consuming_lookahead() -> None:
    """Lookahead returns EOF beyond input and never changes current position."""
    stream = TokenStream(scan_tokens("name + 1"))
    assert stream.peek().kind is TokenKind.IDENTIFIER
    assert stream.peek(1).kind is TokenKind.PLUS
    assert stream.peek(99).kind is TokenKind.EOF
    assert stream.current.kind is TokenKind.IDENTIFIER
    with pytest.raises(ValueError):
        stream.peek(-1)
