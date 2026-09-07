"""Public representation safety, masking and exact length contracts."""

from typing import Any, cast

import pytest

from lclang.utils import safe_repr


class BrokenRepr:
    """Represent an object whose repr raises a process-control exception."""

    def __repr__(self) -> str:
        """Raise to exercise the representation isolation boundary."""
        raise KeyboardInterrupt


def test_representation_handles_rendering_failures_and_newlines() -> None:
    """Renderer output and failures share one protected single-line boundary."""
    assert safe_repr(42) == "42"
    assert safe_repr("ignored", renderer=lambda value: "a\r\nb") == "a\\r\\nb"
    assert safe_repr(BrokenRepr()) == "<repr failed: KeyboardInterrupt>"
    assert safe_repr(0, renderer=lambda value: cast(Any, 7)) == "<repr failed: TypeError>"
    assert safe_repr(0, renderer=lambda value: repr(BrokenRepr())) == (
        "<repr failed: KeyboardInterrupt>"
    )
    assert safe_repr(BrokenRepr(), masked=True) == "*masked*"
    assert safe_repr(0, masked=True, renderer=lambda value: pytest.fail("called")) == "*masked*"


@pytest.mark.parametrize("length", [0, 1, 13, 14, 199, 200, 201])
def test_total_length_includes_the_truncation_marker(length: int) -> None:
    """Every supported budget bounds the escaped output including its marker."""
    text = "x" * 250
    rendered = safe_repr(text, max_length=length, renderer=str)
    marker = "...<truncated>"[:length]
    assert rendered == "x" * (length - len(marker)) + marker
    assert len(rendered) == length
    assert safe_repr("x" * length, max_length=length, renderer=str) == "x" * length
    assert safe_repr(text, max_length=None, renderer=str) == text


@pytest.mark.parametrize("length", [True, "200", 1.5])
def test_invalid_length_types_are_rejected(length: object) -> None:
    """Length is an explicit integer contract rather than a coercion surface."""
    with pytest.raises(TypeError):
        safe_repr(0, max_length=cast(Any, length))


def test_negative_length_is_rejected() -> None:
    """Negative budgets are errors even when the value is masked."""
    with pytest.raises(ValueError):
        safe_repr(0, max_length=-1, masked=True)
