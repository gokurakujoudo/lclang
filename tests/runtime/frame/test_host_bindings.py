"""Behavioural tests for :mod:`lclang.runtime.frame.host_bindings`."""

from typing import Any, cast

import pytest

import lclang


@pytest.mark.asyncio
async def test_mixin_detaches_values_and_updates_direct_lookup() -> None:
    """Sunny: a right-biased mixin is visible without retaining caller state."""
    frame = lclang.define_frame(preset={"value": 1})
    values: dict[str, object] = {"value": 2, "added": 3}

    mixin = cast(Any, frame.mixin)
    result = mixin(values)
    values["added"] = 100

    assert result is None
    assert frame.values == {"value": 2, "added": 3}
    assert await frame.get("value") == 2
    assert await frame.get("added") == 3


@pytest.mark.asyncio
async def test_marked_frame_values_and_mixins_normalize_and_stay_masked() -> None:
    """Host markers are removed from lookup names and survive later updates."""
    frame = lclang.define_frame(preset={"token!": "first"})
    assert await frame.get("token") == "first"
    assert frame.is_masked("token") is True
    frame.mixin({"token": "second", "other!": "third"})
    assert await frame.get("token") == "second"
    assert await frame.get("other") == "third"
    assert frame.masked_names == frozenset({"other"})
    assert frame.is_masked("token") is True
    with pytest.raises(ValueError, match="duplicate"):
        frame.mixin({"same": 1, "same!": 2})


@pytest.mark.asyncio
async def test_mixin_preserves_cached_snapshots_until_recalculation() -> None:
    """Composite: mixed inputs affect direct reads and explicit refresh only."""
    frame = lclang.define_frame(
        lclang.define_module("app", {"result": "host"}),
        preset={"host": 1},
    )
    assert await frame.get("result") == 1

    frame.mixin({"host": 2})

    assert await frame.get("host") == 2
    assert await frame.get("result") == 1
    assert await frame.recalculate("result") == 2
    assert await frame.get("result") == 2


@pytest.mark.asyncio
async def test_definition_precedence_and_child_fallback_survive_mixin() -> None:
    """Definitions still win while descendants observe mixed parent values."""
    parent = lclang.define_frame(
        lclang.define_module("parent", {"defined": "7"}),
    )
    child = parent.derive(
        lclang.define_module("child", {"answer": "defined + mixed"})
    )

    parent.mixin({"defined": 100, "mixed": 5})

    assert await parent.get("defined") == 7
    assert await child.get("answer") == 12


def test_mixin_validates_atomically_and_rejects_wrong_types() -> None:
    """Rainy: invalid updates neither mutate nor partially populate values."""
    frame = lclang.define_frame(preset={"stable": 1})
    before = dict(frame.values)
    with pytest.raises(TypeError):
        frame.mixin(cast(Any, [("value", 2)]))
    with pytest.raises(TypeError, match="mixin names must be strings"):
        frame.mixin(cast(Any, {1: "value"}))
    with pytest.raises(ValueError, match="host binding name cannot be empty"):
        frame.mixin({"valid": 2, "": 3})
    assert frame.values == before


@pytest.mark.asyncio
async def test_mixin_rejects_closed_frames() -> None:
    """Lifecycle safety prevents updates after close begins or completes."""
    frame = lclang.define_frame()
    await frame.close()
    with pytest.raises(lclang.LclClosedFrameError):
        frame.mixin({"value": 1})
