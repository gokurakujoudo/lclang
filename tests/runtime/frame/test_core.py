"""Unit tests mirroring :mod:`lclang.runtime.frame.core`."""

import asyncio
from typing import cast

import pytest

from lclang.errors import LclEvaluationError, LclNameError
from lclang.lang.parser import parse_expression
from lclang.types import FrameId, ModuleName


def test_frame_rejects_empty_frame_and_host_binding_names() -> None:
    """Construction validates both identifier namespaces."""
    from lclang.runtime import Frame, Module

    module = Module(ModuleName("app"), {})
    with pytest.raises(ValueError):
        Frame(module, FrameId(""))
    with pytest.raises(ValueError):
        Frame(module, FrameId("frame:1"), values={"": 1})
    with pytest.raises(TypeError, match="host binding names must be strings"):
        Frame(module, values=cast(dict[str, object], {1: 1}))
    overlay = Frame(module, masked_names={"missing"})
    assert overlay.is_masked("missing") is True
    with pytest.raises(ValueError, match="cannot be empty"):
        Frame(module).is_masked("")


def test_frame_normalizes_optional_and_string_identifiers() -> None:
    """Direct construction shares the ergonomic factory identifier policy."""
    from lclang.runtime import Frame, Module

    module = Module(ModuleName("app"), {})
    assert Frame(module).frame_id == FrameId("frame-app")
    assert Frame(module, "custom").frame_id == FrameId("custom")
    assert Frame(module, native_values=True).native_values is True
    with pytest.raises(TypeError, match="frame identifier must be a string"):
        Frame(module, 42)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="native-values"):
        Frame(module, native_values=1)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_frame_get_rejects_empty_variable_name() -> None:
    """The convenience lookup rejects an ambiguous empty key."""
    from lclang.runtime import Frame, Module

    frame = Frame(Module(ModuleName("app"), {}), FrameId("frame:1"))
    with pytest.raises(ValueError):
        await frame.get("")
    with pytest.raises(ValueError):
        await frame.get("", fallback=42)


@pytest.mark.asyncio
async def test_frame_get_returns_explicit_fallback_for_an_absent_name() -> None:
    """Sunny: any explicit fallback, including None, represents a result."""
    from lclang.runtime import Frame, Module

    marker = object()
    frame = Frame(Module(ModuleName("app"), {}), FrameId("frame:1"))

    assert await frame.get("missing", fallback=marker) is marker
    assert await frame.get("missing", fallback=None) is None
    assert frame.has("missing") is False
    frame.mixin({"missing": 7})
    assert await frame.get("missing", fallback=marker) == 7


@pytest.mark.asyncio
async def test_frame_get_no_fallback_preserves_missing_name_error() -> None:
    """Rainy: omission and the public sentinel retain existing diagnostics."""
    from lclang.runtime import NO_FALLBACK, Frame, Module

    frame = Frame(Module(ModuleName("app"), {}), FrameId("frame:1"))
    with pytest.raises(LclNameError, match="unknown variable: missing"):
        await frame.get("missing")
    with pytest.raises(LclNameError, match="unknown variable: missing"):
        await frame.get("missing", fallback=NO_FALLBACK)


@pytest.mark.asyncio
async def test_frame_get_fallback_does_not_replace_selected_name_outcomes() -> None:
    """Composite: hierarchy hits and definition failures ignore the fallback."""
    from lclang.runtime import Frame, Module

    fallback = object()
    parent = Frame(
        Module(ModuleName("parent"), {}),
        FrameId("parent:1"),
        values={"inherited": 7},
    )
    child_module = Module(
        ModuleName("child"),
        {
            "present": parse_expression("40 + 2"),
            "broken": parse_expression("missing_dependency"),
        },
    )
    async with parent, parent.derive(child_module) as child:
        assert await child.get("inherited", fallback=fallback) == 7
        assert await child.get("present", fallback=fallback) == 42
        with pytest.raises(LclNameError, match="missing_dependency"):
            await child.get("broken", fallback=fallback)


@pytest.mark.asyncio
async def test_frame_lazily_evaluates_and_caches_local_result() -> None:
    """A definition executes once and retains its result by identity."""
    from lclang.runtime import Frame, Module

    calls = 0
    marker = object()

    def produce() -> object:
        nonlocal calls
        calls += 1
        return marker

    module = Module(
        ModuleName("app"),
        {"value": parse_expression("produce()")},
    )
    frame = Frame(module, FrameId("frame:1"), values={"produce": produce})
    assert await frame.get("value") is marker
    assert await frame.get("value") is marker
    assert calls == 1


@pytest.mark.asyncio
async def test_frame_resolves_local_definitions_through_itself() -> None:
    """One local expression can resolve another cached definition."""
    from lclang.runtime import Frame, Module

    module = Module(
        ModuleName("app"),
        {"base": parse_expression("40"), "answer": parse_expression("base + 2")},
    )
    frame = Frame(module, FrameId("frame:1"))
    assert await frame.get("answer") == 42
    assert await frame.get("base") == 40


@pytest.mark.asyncio
async def test_frame_caches_and_reraises_same_failure() -> None:
    """Failed definitions are deterministic snapshots just like values."""
    from lclang.runtime import Frame, Module

    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("broken")

    module = Module(ModuleName("app"), {"value": parse_expression("fail()")})
    frame = Frame(module, FrameId("frame:1"), values={"fail": fail})
    with pytest.raises(LclEvaluationError) as first:
        await frame.get("value")
    with pytest.raises(LclEvaluationError) as second:
        await frame.get("value")
    assert first.value is second.value
    assert calls == 1


@pytest.mark.asyncio
async def test_frame_unknown_name_retains_resolver_span() -> None:
    """Missing definitions report the requesting expression location."""
    from lclang import evaluate
    from lclang.runtime import Frame, Module

    node = parse_expression("missing")
    frame = Frame(Module(ModuleName("app"), {}), FrameId("frame:1"))
    with pytest.raises(LclNameError) as caught:
        await evaluate(node, frame)
    assert caught.value.span == node.span


@pytest.mark.asyncio
async def test_direct_cancellation_is_not_cached() -> None:
    """A cancelled first attempt does not poison the next local lookup."""
    from lclang.runtime import Frame, Module

    calls = 0

    async def sometimes_cancel() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise asyncio.CancelledError
        return 42

    module = Module(ModuleName("app"), {"value": parse_expression("work()")})
    frame = Frame(module, FrameId("frame:1"), values={"work": sometimes_cancel})
    with pytest.raises(asyncio.CancelledError):
        await frame.get("value")
    assert await frame.get("value") == 42


@pytest.mark.asyncio
async def test_child_delegates_parent_result_and_cache_identity() -> None:
    """Ancestor results remain cached and owned by their defining Frame."""
    from lclang.runtime import Frame, Module

    marker = object()
    parent = Frame(
        Module(ModuleName("parent"), {"value": parse_expression("marker")}),
        FrameId("parent:1"),
        values={"marker": marker},
    )
    child = parent.derive(Module(ModuleName("child"), {}))
    assert await child.get("value") is marker
    assert await child.get("value") is await parent.get("value")


@pytest.mark.asyncio
async def test_parent_definition_resolves_inside_parent_scope() -> None:
    """Child shadowing cannot alter an ancestor-owned expression."""
    from lclang.runtime import Frame, Module

    parent_module = Module(
        ModuleName("parent"),
        {"base": parse_expression("40"), "answer": parse_expression("base + 2")},
    )
    child_module = Module(ModuleName("child"), {"base": parse_expression("0")})
    parent = Frame(parent_module, FrameId("parent:1"))
    child = parent.derive(child_module)
    assert await child.get("answer") == 42
    assert await child.get("base") == 0


@pytest.mark.asyncio
async def test_child_definition_can_combine_local_and_parent_values() -> None:
    """Unshadowed names fall through while local names retain precedence."""
    from lclang.runtime import Frame, Module

    parent = Frame(
        Module(ModuleName("parent"), {"base": parse_expression("40")}),
        FrameId("parent:1"),
    )
    child = parent.derive(
        Module(ModuleName("child"), {"answer": parse_expression("base + offset")}),
        {"offset": 2},
    )
    assert await child.get("answer") == 42


@pytest.mark.asyncio
async def test_missing_parent_chain_keeps_original_request_span() -> None:
    """Hierarchical fallback does not replace the requesting name-node span."""
    from lclang import evaluate
    from lclang.runtime import Frame, Module

    empty = Module(ModuleName("empty"), {})
    parent = Frame(empty, FrameId("parent:1"))
    child = parent.derive(empty)
    node = parse_expression("missing")
    with pytest.raises(LclNameError) as caught:
        await evaluate(node, child)
    assert caught.value.span == node.span
