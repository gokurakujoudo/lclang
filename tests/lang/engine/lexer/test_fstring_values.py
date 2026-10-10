"""Unit tests mirroring :mod:`lclang.lang.engine.lexer.fstring_parts`."""

from dataclasses import FrozenInstanceError

import pytest

from lclang.lang.engine.lexer.fstring_parts import FStringField, FStringText, FStringValue


def test_lexical_fstring_values_are_frozen_and_structural() -> None:
    """Scanner results compare by value and cannot be modified downstream."""
    value = FStringValue((FStringText("x"), FStringField("name")), raw=False)
    assert value == FStringValue((FStringText("x"), FStringField("name")), raw=False)
    with pytest.raises(FrozenInstanceError):
        value.raw = True  # type: ignore[misc]
