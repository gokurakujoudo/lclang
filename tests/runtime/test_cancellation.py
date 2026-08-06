"""Cancellation isolation tests for shared Frame owner tasks."""

import asyncio

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import Frame, Module
from pylcl.types import FrameId, ModuleName


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_owner() -> None:
    """One cancelled caller leaves its peer and cache completion intact."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def work() -> int:
        started.set()
        await release.wait()
        return 42

    module = Module(ModuleName("app"), {"value": parse_expression("work()")})
    frame = Frame(module, FrameId("frame:1"), values={"work": work})
    cancelled = asyncio.create_task(frame.get("value"))
    survivor = asyncio.create_task(frame.get("value"))
    await started.wait()
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    release.set()
    assert await survivor == 42
    assert await frame.get("value") == 42


@pytest.mark.asyncio
async def test_owner_cancellation_reaches_waiters_and_allows_retry() -> None:
    """Definition-originated cancellation is shared but never cached."""
    calls = 0

    async def work() -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        if calls == 1:
            raise asyncio.CancelledError
        return 42

    module = Module(ModuleName("app"), {"value": parse_expression("work()")})
    frame = Frame(module, FrameId("frame:1"), values={"work": work})
    outcomes = await asyncio.gather(
        frame.get("value"),
        frame.get("value"),
        return_exceptions=True,
    )
    assert all(isinstance(outcome, asyncio.CancelledError) for outcome in outcomes)
    assert await frame.get("value") == 42
    assert calls == 2
