"""Immutable module composition and lazy override reservations."""

from typing import Any, cast

import pytest

from lclang.common.identifiers import ModuleName
from lclang.error import LclEvaluationError, LclValidationError
from lclang.lang import NEED_OVERRIDE, RUNTIME_OVERRIDE, define_frame, define_module
from lclang.lang.runtime import Module, VariableInspectionStatus


@pytest.mark.asyncio
async def test_module_mixin_creates_new_right_biased_snapshot() -> None:
    """Composition changes dependants without changing existing Modules or Frames."""
    original = define_module("base", {"x": "1", "result": "x + 1"})
    replacement = define_module("patch", {"x": "10"})
    combined = original.mixin(replacement)
    assert combined.name == original.name
    assert list(combined.definitions) == ["x", "result"]
    async with define_frame(original) as before, define_frame(combined) as after:
        assert await before.get("result") == 2
        assert await after.get("result") == 11


@pytest.mark.asyncio
async def test_need_override_is_lazy_and_blocks_preset_fallback() -> None:
    """Only an actual definition override satisfies a required configuration value."""
    module = define_module("required", {"a": "NEED_OVERRIDE", "b": "a if False else 100"})
    async with define_frame(module, preset={"a": 42}) as frame:
        assert await frame.get("b") == 100
        with pytest.raises(LclEvaluationError, match="a needs a value"):
            await frame.get("a")


@pytest.mark.asyncio
async def test_runtime_override_accepts_code_values_and_explicit_none() -> None:
    """Runtime reservations preserve ordinary host values, including None."""
    module = define_module("runtime", {"a": "RUNTIME_OVERRIDE", "result": "a"})
    async with define_frame(module, preset={"a": None}) as frame:
        assert await frame.get("result") is None
    async with define_frame(module) as frame:
        frame.mixin({"a": 42})
        assert await frame.get("result") == 42


def test_module_mixin_validates_arguments_and_preserves_masks_namespaces() -> None:
    """Composition validates a new immutable structure before any Frame exists."""
    base = define_module("base", {"secret!": "1"})
    patch = Module(
        ModuleName("patch"),
        define_module("values", {"secret": "2"}).definitions,
        namespace_names=frozenset({"empty"}),
    )
    combined = base.mixin(patch, name="deployment")
    assert combined.name == "deployment"
    assert combined.masked_names == frozenset({"secret"})
    assert combined.namespace_names == frozenset({"empty"})
    assert list(combined.definitions) == ["secret", "empty"]
    with pytest.raises(LclValidationError):
        base.mixin(cast(Any, {}))
    with pytest.raises(LclValidationError):
        base.mixin(patch, name=cast(Any, 1))
    with pytest.raises(LclValidationError):
        base.mixin(patch, name="")
    with pytest.raises(LclValidationError, match="namespace"):
        combined.mixin(define_module("invalid", {"empty": "1"}))
    with pytest.raises(LclValidationError):
        Module(ModuleName("invalid"), {}, namespace_names=cast(Any, set()))
    with pytest.raises(LclValidationError, match="reserved"):
        Module(ModuleName("invalid"), {}, namespace_names=frozenset({"__private"}))


@pytest.mark.asyncio
async def test_python_markers_and_runtime_provider_after_cached_failure() -> None:
    """Late host values replace a failed reservation in lookup and inspection."""
    assert repr(NEED_OVERRIDE) == "NEED_OVERRIDE"
    module = define_module("runtime", {"a": RUNTIME_OVERRIDE, "required": NEED_OVERRIDE})
    async with define_frame(module) as frame:
        with pytest.raises(LclEvaluationError):
            await frame.get("a")
        frame.mixin({"a": None})
        assert await frame.get("a") is None
        assert frame.get_definition("a") is None
        assert frame.inspect_variable("a").status is VariableInspectionStatus.EXTERNAL_PROVIDED
        with pytest.raises(LclEvaluationError, match="host binding"):
            frame.dependency_snapshot("a")
        with pytest.raises(LclEvaluationError, match="host binding"):
            await frame.recalculate("a")


@pytest.mark.asyncio
async def test_multiple_runtime_reservations_find_lower_actual_value() -> None:
    """Repeated reservation layers do not hide the eventual runtime provider."""
    module = define_module("runtime", {"a": RUNTIME_OVERRIDE})
    async with define_frame(module, preset={"a": 12}) as parent, parent.derive(module) as child:
        assert await child.get("a") == 12
