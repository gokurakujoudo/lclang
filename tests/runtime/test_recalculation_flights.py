"""Initial-owner and waiter coordination for explicit recalculation."""

import asyncio

import pytest

from pylcl.errors import LclEvaluationError
from pylcl.lang.parser import parse_expression
from pylcl.runtime import Frame, Module
from pylcl.types import FrameId, ModuleName


def _frame(work: object) -> Frame:
    module = Module(ModuleName("app"), {"value": parse_expression("work()")})
    return Frame(module, FrameId("frame:1"), values={"work": work})


@pytest.mark.asyncio
async def test_recalculations_wait_for_and_follow_initial_owner() -> None:
    """Concurrent refreshes settle initial work then share one new owner."""
    initial_release = asyncio.Event()
    refresh_started = asyncio.Event()
    refresh_release = asyncio.Event()
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            await initial_release.wait()
        else:
            refresh_started.set()
            await refresh_release.wait()
        return calls

    frame = _frame(work)
    initial = asyncio.create_task(frame.get("value"))
    await asyncio.sleep(0)
    first = asyncio.create_task(frame.recalculate("value"))
    second = asyncio.create_task(frame.recalculate("value"))
    await asyncio.sleep(0)
    initial_release.set()
    assert await initial == 1
    await refresh_started.wait()
    refresh_release.set()
    assert await first == 2
    assert await second == 2
    assert calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_initial", [False, True])
async def test_failed_or_cancelled_initial_owner_is_followed_by_refresh(
    cancel_initial: bool,
) -> None:
    """Any owner-originated non-result settlement permits a fresh attempt."""
    release = asyncio.Event()
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            await release.wait()
            if cancel_initial:
                raise asyncio.CancelledError
            raise ValueError("initial failure")
        return 42

    frame = _frame(work)
    initial = asyncio.create_task(frame.get("value"))
    await asyncio.sleep(0)
    refresh = asyncio.create_task(frame.recalculate("value"))
    await asyncio.sleep(0)
    release.set()
    outcome = await asyncio.gather(initial, return_exceptions=True)
    expected = asyncio.CancelledError if cancel_initial else LclEvaluationError
    assert isinstance(outcome[0], expected)
    assert await refresh == 42
    assert calls == 2


@pytest.mark.asyncio
async def test_cancelled_recalculation_waiter_leaves_initial_owner_alive() -> None:
    """Caller cancellation while waiting does not cancel initial evaluation."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def work() -> int:
        started.set()
        await release.wait()
        return 42

    frame = _frame(work)
    initial = asyncio.create_task(frame.get("value"))
    await started.wait()
    refresh = asyncio.create_task(frame.recalculate("value"))
    await asyncio.sleep(0)
    refresh.cancel()
    with pytest.raises(asyncio.CancelledError):
        await refresh
    release.set()
    assert await initial == 42
    assert await frame.get("value") == 42
