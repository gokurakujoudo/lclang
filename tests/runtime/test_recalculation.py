"""Unit tests for atomic :class:`pylcl.runtime.Frame` recalculation."""

import asyncio

import pytest

from pylcl.errors import LclEvaluationError, LclNameError
from pylcl.lang.parser import parse_expression
from pylcl.runtime import Frame, Module
from pylcl.types import FrameId, ModuleName


def _frame(definitions: dict[str, str], **values: object) -> Frame:
    nodes = {name: parse_expression(source) for name, source in definitions.items()}
    return Frame(Module(ModuleName("app"), nodes), FrameId("frame:1"), values=values)


@pytest.mark.asyncio
async def test_recalculation_replaces_only_requested_snapshot() -> None:
    """A refreshed dependency does not invalidate its cached dependant."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return calls

    frame = _frame({"base": "produce()", "dependant": "base + 1"}, produce=produce)
    assert await frame.get("dependant") == 2
    assert await frame.recalculate("base") == 2
    assert await frame.get("base") == 2
    assert await frame.get("dependant") == 2


@pytest.mark.asyncio
async def test_previous_value_remains_visible_until_atomic_commit() -> None:
    """Ordinary lookup observes the old result while refresh is running."""
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            started.set()
            await release.wait()
        return calls

    frame = _frame({"value": "work()"}, work=work)
    assert await frame.get("value") == 1
    refresh = asyncio.create_task(frame.recalculate("value"))
    await started.wait()
    assert await frame.get("value") == 1
    release.set()
    assert await refresh == 2
    assert await frame.get("value") == 2


@pytest.mark.asyncio
async def test_refresh_failure_atomically_replaces_prior_result() -> None:
    """An ordinary failed refresh becomes the new cached snapshot."""
    calls = 0

    def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("new failure")
        return calls

    frame = _frame({"value": "work()"}, work=work)
    assert await frame.get("value") == 1
    with pytest.raises(LclEvaluationError) as refresh:
        await frame.recalculate("value")
    with pytest.raises(LclEvaluationError) as cached:
        await frame.get("value")
    assert cached.value is refresh.value


@pytest.mark.asyncio
async def test_concurrent_recalculations_share_one_refresh_owner() -> None:
    """Concurrent explicit refresh callers execute the definition once."""
    release = asyncio.Event()
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            await release.wait()
        return calls

    frame = _frame({"value": "work()"}, work=work)
    assert await frame.get("value") == 1
    first = asyncio.create_task(frame.recalculate("value"))
    second = asyncio.create_task(frame.recalculate("value"))
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(first, second)
    assert results[0] == 2
    assert results[1] == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_cancelled_refresh_preserves_snapshot_and_can_retry() -> None:
    """Owner cancellation commits nothing and removes refresh flight state."""
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise asyncio.CancelledError
        return calls

    frame = _frame({"value": "work()"}, work=work)
    assert await frame.get("value") == 1
    with pytest.raises(asyncio.CancelledError):
        await frame.recalculate("value")
    assert await frame.get("value") == 1
    assert await frame.recalculate("value") == 3


@pytest.mark.asyncio
async def test_child_recalculates_definition_in_parent_owner() -> None:
    """Hierarchy refresh delegates to the Frame that owns the definition."""
    calls = 0

    def work() -> int:
        nonlocal calls
        calls += 1
        return calls

    parent = _frame({"value": "work()"}, work=work)
    child = Frame(
        Module(ModuleName("child"), {}),
        FrameId("child:1"),
        parent=parent,
    )
    assert await child.get("value") == 1
    assert await child.recalculate("value") == 2
    assert await parent.get("value") == 2


@pytest.mark.asyncio
async def test_recalculation_rejects_invalid_or_non_definition_names() -> None:
    """Empty, host-only, and unknown names retain distinct diagnostics."""
    frame = _frame({}, host=42)
    with pytest.raises(ValueError):
        await frame.recalculate("")
    with pytest.raises(LclEvaluationError):
        await frame.recalculate("host")
    with pytest.raises(LclNameError):
        await frame.recalculate("missing")
