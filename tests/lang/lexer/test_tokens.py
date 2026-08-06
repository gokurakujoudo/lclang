"""Unit tests mirroring :mod:`pylcl.lang.lexer.tokens`."""

from dataclasses import FrozenInstanceError

import pytest

from pylcl.lang.lexer import Token, TokenKind
from pylcl.source import UNKNOWN_SPAN


def test_token_is_an_immutable_source_value() -> None:
    """Tokens preserve exact source text and cannot be changed."""
    token = Token(TokenKind.IDENTIFIER, "answer", UNKNOWN_SPAN)
    assert token.lexeme == "answer"
    assert token.value is None
    assert token.span is UNKNOWN_SPAN
    with pytest.raises(FrozenInstanceError):
        token.lexeme = "other"  # type: ignore[misc]


def test_token_kind_names_are_stable() -> None:
    """Representative public kind names remain suitable for diagnostics."""
    assert TokenKind.IDENTIFIER.value == "identifier"
    assert TokenKind.KW_TRUE.value == "true"
    assert TokenKind.QUESTION_DOT.value == "?."
    assert TokenKind.EOF.value == "end of input"
