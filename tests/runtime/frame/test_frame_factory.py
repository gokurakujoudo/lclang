"""Unit tests mirroring :mod:`lclang.runtime.frame.frame_factory`."""

from dataclasses import FrozenInstanceError

import pytest

from lclang.lang.parser import parse_expression
from lclang.runtime import EvaluationLimits, FrameFactory, Module, Preset
from lclang.types import FrameId, ModuleName


def _module(source: str = "base + extra") -> Module:
    return Module(ModuleName("app"), {"value": parse_expression(source)})


@pytest.mark.asyncio
async def test_factory_applies_preset_then_call_level_value_overrides() -> None:
    """Effective host bindings follow explicit right-biased precedence."""
    factory = FrameFactory(_module(), Preset("base", {"base": 1, "extra": 2}))
    frame = factory.create(FrameId("frame:1"), values={"extra": 4})
    assert await frame.get("value") == 5
    assert frame.values == {"base": 1, "extra": 4}


@pytest.mark.asyncio
async def test_each_create_has_independent_cache_and_lifecycle_state() -> None:
    """Closing or evaluating one product cannot affect another factory product."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return calls

    factory = FrameFactory(_module("produce()"), Preset("host", {"produce": produce}))
    first = factory.create(FrameId("first"))
    second = factory.create(FrameId("second"))
    assert await first.get("value") == 1
    assert await second.get("value") == 2
    await first.close()
    assert await second.get("value") == 2


def test_create_defaults_the_frame_id_from_the_module_name() -> None:
    """Omitting boilerplate produces one deterministic diagnostic identifier."""
    factory = FrameFactory(_module("1"))
    first = factory.create()
    second = factory.create()
    assert first.frame_id == FrameId("frame-app")
    assert second.frame_id == FrameId("frame-app")
    assert first is not second


def test_factory_routes_parent_and_limit_precedence_without_ownership() -> None:
    """Create forwards parent and chooses call, factory, then Frame defaults."""
    parent = FrameFactory(_module("1")).create(FrameId("parent"))
    default_limits = EvaluationLimits(
        max_depth=2, max_steps=3, max_collection_items=4
    )
    override = EvaluationLimits(max_depth=5, max_steps=6, max_collection_items=7)
    factory = FrameFactory(_module(), limits=default_limits)
    inherited = factory.create(FrameId("one"), parent=parent)
    explicit = factory.create(FrameId("two"), parent=parent, limits=override)
    implicit = FrameFactory(_module()).create(FrameId("three"))
    assert inherited.parent is explicit.parent is parent
    assert inherited.limits is default_limits
    assert explicit.limits is override
    assert implicit.limits == EvaluationLimits()


def test_factory_retains_a_default_parent_and_allows_call_override() -> None:
    """Reusable parent policy survives composition and yields to a call parent."""
    default_parent = FrameFactory(_module("1")).create(FrameId("default-parent"))
    call_parent = FrameFactory(_module("2")).create(FrameId("call-parent"))
    factory = FrameFactory(_module(), parent=default_parent)
    inherited = factory.create(FrameId("inherited"))
    overridden = factory.create(FrameId("overridden"), parent=call_parent)
    composed = factory.with_preset(Preset("values", {"extra": 3}))
    assert inherited.parent is default_parent
    assert overridden.parent is call_parent
    assert composed.parent is default_parent


def test_with_preset_returns_a_new_composed_factory() -> None:
    """Factory policy composition never mutates its reusable input policy."""
    original = FrameFactory(_module(), Preset("base", {"base": 1, "extra": 2}))
    updated = original.with_preset(Preset("local", {"extra": 4}))
    empty = FrameFactory(_module()).with_preset(Preset("only", {"base": 3}))
    assert original.preset is not None
    assert original.preset.values["extra"] == 2
    assert updated.preset is not None
    assert updated.preset.values["extra"] == 4
    assert updated.preset.name == "base+local"
    assert empty.preset is not None and empty.preset.name == "only"
    with pytest.raises(FrozenInstanceError):
        original.module = _module("0")  # type: ignore[misc]


def test_factory_validates_policy_types_and_delegates_frame_identifiers() -> None:
    """Invalid policy objects fail early while Frame keeps identifier validation."""
    with pytest.raises(TypeError):
        FrameFactory(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FrameFactory(_module(), object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FrameFactory(_module(), limits=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        FrameFactory(_module(), parent=object())  # type: ignore[arg-type]
    factory = FrameFactory(_module())
    with pytest.raises(TypeError):
        factory.with_preset(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        factory.create(FrameId("frame"), limits=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        factory.create(FrameId("frame"), parent=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        factory.create(FrameId(""))
