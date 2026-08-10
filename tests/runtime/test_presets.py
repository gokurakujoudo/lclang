"""Unit tests mirroring :mod:`lclang.runtime.presets`."""

from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from lclang.runtime import Preset


def test_preset_detaches_an_ordered_read_only_binding_snapshot() -> None:
    """Caller mapping changes cannot mutate a validated preset."""
    values: dict[str, object] = {"first": 1}
    preset = Preset("base", values)
    values["first"] = 2
    assert preset.values == {"first": 1}
    opaque_values: object = preset.values
    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], opaque_values)["other"] = 3
    with pytest.raises(FrozenInstanceError):
        preset.name = "other"  # type: ignore[misc]


@pytest.mark.parametrize(("name", "values"), [("", {}), ("base", {"": 1})])
def test_preset_rejects_empty_public_names(
    name: str,
    values: dict[str, object],
) -> None:
    """Preset and binding identifiers must be non-empty."""
    with pytest.raises(ValueError):
        Preset(name, values)


def test_overlay_is_shallow_ordered_and_right_biased() -> None:
    """A new overlay replaces collisions without mutating opaque mapped values."""
    opaque = {"nested": 1}
    left = Preset("base", {"first": 1, "shared": "old", "opaque": opaque})
    right = Preset("local", {"shared": "new", "last": 3})
    combined = left.overlay(right)
    assert combined.name == "base+local"
    assert tuple(combined.values) == ("first", "shared", "opaque", "last")
    assert combined.values["shared"] == "new"
    assert combined.values["opaque"] is opaque
    assert left.values["shared"] == "old"


def test_overlay_accepts_an_explicit_name_and_validates_inputs() -> None:
    """Callers may publish one durable name for a composed preset."""
    preset = Preset("base", {"value": 1})
    other = Preset("local", {"value": 2})
    assert preset.overlay(other, name="effective").name == "effective"
    with pytest.raises(ValueError):
        preset.overlay(other, name="")
    with pytest.raises(TypeError):
        preset.overlay(object())  # type: ignore[arg-type]
