"""Unit tests mirroring :mod:`pylcl.stdlib.data`."""

import pytest

from pylcl.stdlib import lookup, merge


def test_merge_is_shallow_ordered_right_biased_and_read_only() -> None:
    """Later mappings replace values without recursively copying them."""
    opaque = {"nested": 1}
    result = merge(
        {"first": 1, "shared": "old", "opaque": opaque},
        {"shared": "new", "last": 3},
    )
    assert tuple(result) == ("first", "shared", "opaque", "last")
    assert result["shared"] == "new"
    assert result["opaque"] is opaque
    with pytest.raises(TypeError):
        result["other"] = 4  # type: ignore[index]


def test_merge_rejects_non_mappings_and_accepts_no_inputs() -> None:
    """An empty merge is valid while every supplied value must be a Mapping."""
    assert merge() == {}
    with pytest.raises(TypeError):
        merge({"value": 1}, object())  # type: ignore[arg-type]


def test_lookup_returns_present_values_or_the_explicit_default() -> None:
    """Missing keys use the caller default without suppressing protocol errors."""
    marker = object()
    assert lookup({"value": None}, "value", marker) is None
    assert lookup({}, "missing", marker) is marker
    with pytest.raises(TypeError):
        lookup(object(), "value")  # type: ignore[arg-type]
