"""Event-controlled Frame concurrency and lifecycle stress tests."""

from __future__ import annotations

import asyncio

import pytest

import lclang
from tests.support.concurrency import AsyncCloseProbe, CountingGate


@pytest.mark.asyncio
async def test_two_hundred_fifty_six_waiters_share_owner_despite_cancellation() -> None:
    """Cancelling half the peers leaves one owner and equal survivors."""
    gate = CountingGate(42)
    frame = lclang.Frame(
        lclang.define_module("lookup-stress", {"result": "work()"}),
        values={"work": gate.run},
    )
    requests = [asyncio.create_task(frame.get("result")) for _ in range(256)]
    await gate.started.wait()
    for request in requests[:128]:
        request.cancel()
    gate.release.set()
    outcomes = await asyncio.gather(*requests, return_exceptions=True)
    assert all(isinstance(value, asyncio.CancelledError) for value in outcomes[:128])
    assert outcomes[128:] == [42] * 128
    assert gate.calls == 1
    await frame.close()


@pytest.mark.asyncio
async def test_sixty_four_refreshes_coalesce_without_invalidating_dependant() -> None:
    """One refresh atomically replaces only its selected cached snapshot."""
    gate = CountingGate(1, block_after=1)
    frame = lclang.Frame(
        lclang.define_module(
            "refresh-stress",
            {"base": "work()", "dependant": "base + 1"},
        ),
        values={"work": gate.run},
    )
    assert await frame.get("dependant") == 2
    refreshes = [asyncio.create_task(frame.recalculate("base")) for _ in range(64)]
    await gate.started.wait()
    gate.value = 2
    gate.release.set()
    assert await asyncio.gather(*refreshes) == [2] * 64
    assert gate.calls == 2
    assert await frame.get("dependant") == 2
    assert await frame.get("base") == 2
    await frame.close()


@pytest.mark.asyncio
async def test_close_race_cancels_work_and_closes_resource_once() -> None:
    """Cancelled close waiters cannot interrupt shared deterministic cleanup."""
    slow = CountingGate(99)
    resource = AsyncCloseProbe()
    frame = lclang.Frame(
        lclang.define_module(
            "close-stress",
            {"owned": "make()", "slow": "work()"},
        ),
        values={"make": lambda: resource, "work": slow.run},
    )
    assert await frame.get("owned") is resource
    lookup = asyncio.create_task(frame.get("slow"))
    await slow.started.wait()
    closers = [asyncio.create_task(frame.close()) for _ in range(64)]
    await resource.close_started.wait()
    for closer in closers[:32]:
        closer.cancel()
    resource.release.set()
    outcomes = await asyncio.gather(*closers, return_exceptions=True)
    lookup_outcome = await asyncio.gather(lookup, return_exceptions=True)
    assert all(isinstance(value, asyncio.CancelledError) for value in outcomes[:32])
    assert outcomes[32:] == [None] * 32
    assert isinstance(lookup_outcome[0], asyncio.CancelledError)
    assert resource.close_calls == 1
    assert frame.closed is True
    remaining = asyncio.all_tasks() - {asyncio.current_task()}
    assert all(task.done() for task in remaining)
