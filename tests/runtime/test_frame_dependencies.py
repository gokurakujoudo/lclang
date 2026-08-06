"""Tests mirroring :mod:`pylcl.runtime.frame_dependencies`."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from pylcl.errors import LclClosedFrameError, LclEvaluationError, LclNameError
from pylcl.lang.parser import parse_expression
from pylcl.runtime import DependencyKind, Frame, Module
from pylcl.types import FrameId, ModuleName, VarName


def _frame(definitions: dict[str, str], **values: object) -> Frame:
    nodes = {name: parse_expression(source) for name, source in definitions.items()}
    return Frame(Module(ModuleName("app"), nodes), FrameId("frame:1"), values=values)


def _targets(frame: Frame, name: str) -> tuple[VarName, ...]:
    return tuple(edge.target for edge in frame.dependency_snapshot(name).dynamic_edges)


@pytest.mark.asyncio
async def test_snapshot_moves_static_occurrences_from_inactive_to_confirmed() -> None:
    """Conditional execution publishes only the name occurrences actually used."""
    frame = _frame(
        {"value": "left if flag else right"}, flag=False, left=1, right=2
    )
    before = frame.dependency_snapshot("value")
    assert before.dynamic_edges == ()
    assert before.reconciliation.inactive == before.static_edges
    assert await frame.get("value") == 2
    after = frame.dependency_snapshot("value")
    assert tuple(edge.target for edge in after.dynamic_edges) == (
        VarName("flag"),
        VarName("right"),
    )
    assert tuple(edge.kind for edge in after.reconciliation.confirmed) == (
        DependencyKind.EAGER,
        DependencyKind.CONDITIONAL,
    )
    assert before.dynamic_edges == ()


@pytest.mark.asyncio
async def test_nested_and_cached_evaluation_attributes_each_defining_source() -> None:
    """Dependency owners trace independently and cache hits add no observations."""
    frame = _frame({"base": "host", "result": "base + base"}, host=3)
    assert await frame.get("result") == 6
    assert _targets(frame, "base") == (VarName("host"),)
    result_targets = _targets(frame, "result")
    assert result_targets == (VarName("base"), VarName("base"))
    assert await frame.get("result") == 6
    assert _targets(frame, "result") == result_targets


@pytest.mark.asyncio
async def test_failure_and_later_closure_lookup_are_published() -> None:
    """Ordinary failures and delayed free-name resolution remain observable."""
    failed = _frame({"value": "missing"})
    with pytest.raises(LclNameError):
        await failed.get("value")
    assert _targets(failed, "value") == (VarName("missing"),)

    closure = _frame({"function": "def (x): x + outer"}, outer=40)
    function = await closure.get("function")
    initial = closure.dependency_snapshot("function")
    call = cast(Callable[..., Awaitable[object]], function)
    assert await call(2) == 42
    assert initial.dynamic_edges == ()
    assert _targets(closure, "function") == (VarName("outer"),)


@pytest.mark.asyncio
async def test_successful_recalculation_atomically_replaces_trace() -> None:
    """Inspection sees old evidence until the fresh value and trace commit."""
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def choose() -> bool:
        nonlocal calls
        calls += 1
        if calls == 2:
            started.set()
            await release.wait()
        return calls == 2

    frame = _frame(
        {"value": "left if choose() else right"}, choose=choose, left=1, right=2
    )
    assert await frame.get("value") == 2
    old = frame.dependency_snapshot("value")
    refresh = asyncio.create_task(frame.recalculate("value"))
    await started.wait()
    assert frame.dependency_snapshot("value") == old
    release.set()
    assert await refresh == 1
    assert _targets(frame, "value") == (VarName("choose"), VarName("left"))
    assert tuple(edge.target for edge in old.dynamic_edges)[-1] == VarName("right")


@pytest.mark.asyncio
async def test_failed_recalculation_replaces_and_cancellation_preserves_trace() -> None:
    """Ordinary failure commits candidate evidence; owner cancellation does not."""
    calls = 0

    async def choose() -> bool:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise asyncio.CancelledError
        return calls == 2

    frame = _frame(
        {"value": "missing if choose() else right"}, choose=choose, right=2
    )
    assert await frame.get("value") == 2
    with pytest.raises(LclNameError):
        await frame.recalculate("value")
    failed = frame.dependency_snapshot("value")
    assert _targets(frame, "value") == (VarName("choose"), VarName("missing"))
    with pytest.raises(asyncio.CancelledError):
        await frame.recalculate("value")
    assert frame.dependency_snapshot("value") == failed


@pytest.mark.asyncio
async def test_snapshot_routes_to_owner_and_rejects_invalid_lifecycle_names() -> None:
    """Hierarchy, host, unknown, empty, and closed cases retain clear errors."""
    parent = _frame({"value": "host"}, host=7)
    child = Frame(
        Module(ModuleName("child"), {}),
        FrameId("child:1"),
        values={"local_host": 1},
        parent=parent,
    )
    assert child.dependency_snapshot("value") == parent.dependency_snapshot("value")
    with pytest.raises(ValueError):
        child.dependency_snapshot("")
    with pytest.raises(LclEvaluationError):
        child.dependency_snapshot("local_host")
    with pytest.raises(LclNameError):
        child.dependency_snapshot("missing")
    await child.close()
    with pytest.raises(LclClosedFrameError):
        child.dependency_snapshot("value")
