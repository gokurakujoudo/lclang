"""Unit tests mirroring :mod:`lclang.lang.lexer.fstring_values`."""

from dataclasses import FrozenInstanceError

import pytest

from lclang.lang.lexer.fstring_values import FStringField, FStringText, FStringValue


def test_lexical_fstring_values_are_frozen_and_structural() -> None:
    """Scanner results compare by value and cannot be modified downstream."""
    value = FStringValue((FStringText("x"), FStringField("name")), raw=False)
    assert value == FStringValue((FStringText("x"), FStringField("name")), raw=False)
    with pytest.raises(FrozenInstanceError):
        value.raw = True  # type: ignore[misc]
