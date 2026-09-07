"""Unit tests mirroring :mod:`lclang.runtime.frame.cache_lifecycle`."""

import asyncio

import pytest

from lclang import evaluate
from lclang.errors import LclClosedFrameError, LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.runtime import Frame, Module
from lclang.types import FrameId, ModuleName
from tests.runtime.frame.lifecycle_support import (
    AsyncResource,
    BlockingResource,
    CancellingResource,
    SyncResource,
)


def _frame(definitions: dict[str, str], **values: object) -> Frame:
    nodes = {name: parse_expression(source) for name, source in definitions.items()}
    return Frame(Module(ModuleName("app"), nodes), FrameId("frame:1"), values=values)


@pytest.mark.asyncio
async def test_close_rejects_all_evaluation_boundaries() -> None:
    """A closed Frame permanently rejects lookup and recalculation."""
    frame = _frame({"value": "1"})
    assert bool(frame.closed) is False
    await frame.close()
    assert bool(frame.closed) is True
    with pytest.raises(LclClosedFrameError):
        await frame.get("value")
    with pytest.raises(LclClosedFrameError):
        await frame.get("missing", fallback=None)
    with pytest.raises(LclClosedFrameError):
        await frame.recalculate("value")
    node = parse_expression("value")
    with pytest.raises(LclClosedFrameError) as caught:
        await evaluate(node, frame)
    assert caught.value.span == node.span
    await frame.close()


@pytest.mark.asyncio
async def test_async_context_manager_returns_frame_and_closes_resources() -> None:
    """Sunny: entering returns the Frame and normal exit releases its results."""
    events: list[str] = []
    resource = AsyncResource("resource", events)
    frame = _frame({"resource": "make()"}, make=lambda: resource)

    async with frame as entered:
        assert entered is frame
        assert await entered.get("resource") is resource
        assert entered.closed is False

    assert frame.closed is True
    assert events == ["resource"]


@pytest.mark.asyncio
async def test_async_context_manager_closes_without_suppressing_body_error() -> None:
    """Rainy: exceptional exit closes the Frame and preserves the body error."""
    frame = _frame({"value": "1"})

    with pytest.raises(RuntimeError, match="body failed"):
        async with frame:
            raise RuntimeError("body failed")

    assert frame.closed is True


@pytest.mark.asyncio
async def test_close_cancels_and_awaits_owned_evaluation() -> None:
    """Owner finalization completes before Frame close returns."""
    started = asyncio.Event()
    finalized = asyncio.Event()

    async def work() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    frame = _frame({"value": "work()"}, work=work)
    waiter = asyncio.create_task(frame.get("value"))
    await started.wait()
    await frame.close()
    assert finalized.is_set()
    with pytest.raises(asyncio.CancelledError):
        await waiter


@pytest.mark.asyncio
async def test_resources_close_in_reverse_order_once_by_identity() -> None:
    """Owned sync/async results unwind in reverse and shared values deduplicate."""
    events: list[str] = []
    first = SyncResource("first", events)
    shared = AsyncResource("shared", events)
    host = SyncResource("host", events)
    frame = _frame(
        {"first": "make_first()", "second": "make_shared()", "third": "make_shared()"},
        make_first=lambda: first,
        make_shared=lambda: shared,
        host=host,
    )
    await frame.get("first")
    await frame.get("second")
    await frame.get("third")
    await frame.close()
    assert events == ["shared", "first"]
    assert shared.calls == 1
    assert first.calls == 1
    assert host.calls == 0


@pytest.mark.asyncio
async def test_cancelled_close_waiter_does_not_abort_cleanup() -> None:
    """The owned close Task survives cancellation of an individual caller."""
    resource = BlockingResource()
    frame = _frame({"resource": "make()"}, make=lambda: resource)
    await frame.get("resource")
    first = asyncio.create_task(frame.close())
    await resource.started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert bool(frame.closed) is False
    second = asyncio.create_task(frame.close())
    resource.release.set()
    await second
    assert bool(frame.closed) is True
    assert resource.calls == 1


@pytest.mark.asyncio
async def test_cleanup_failure_attempts_all_resources_and_is_stable() -> None:
    """The first cleanup failure is cached after every resource is attempted."""
    events: list[str] = []
    first = SyncResource("first", events)
    broken = SyncResource("broken", events, ValueError("cleanup failed"))
    frame = _frame(
        {"first": "first_resource()", "broken": "broken_resource()"},
        first_resource=lambda: first,
        broken_resource=lambda: broken,
    )
    await frame.get("first")
    await frame.get("broken")
    with pytest.raises(LclEvaluationError) as initial:
        await frame.close()
    assert bool(frame.closed) is True
    assert events == ["broken", "first"]
    with pytest.raises(LclEvaluationError) as repeated:
        await frame.close()
    assert repeated.value is initial.value
    assert events == ["broken", "first"]


@pytest.mark.asyncio
async def test_cleanup_cancellation_still_attempts_remaining_resources() -> None:
    """Direct cleanup cancellation closes state after visiting every resource."""
    events: list[str] = []
    remaining = SyncResource("remaining", events)
    cancelling = CancellingResource(events)
    frame = _frame(
        {"remaining": "remaining_resource()", "cancel": "cancel_resource()"},
        remaining_resource=lambda: remaining,
        cancel_resource=lambda: cancelling,
    )
    await frame.get("remaining")
    await frame.get("cancel")
    with pytest.raises(asyncio.CancelledError):
        await frame.close()
    assert bool(frame.closed) is True
    assert events == ["cancel", "remaining"]


@pytest.mark.asyncio
async def test_child_close_borrows_parent_but_parent_close_blocks_fallback() -> None:
    """Hierarchy ownership is directional rather than cascading."""
    parent = _frame({"value": "42"})
    child = parent.derive(Module(ModuleName("child"), {}))
    await child.close()
    assert await parent.get("value") == 42
    open_child = parent.derive(Module(ModuleName("other"), {}))
    await parent.close()
    with pytest.raises(LclClosedFrameError):
        await open_child.get("value")


@pytest.mark.asyncio
async def test_recalculation_retains_displaced_resource_until_close() -> None:
    """Both current and retired owned snapshots are eventually released."""
    events: list[str] = []
    resources = iter((SyncResource("old", events), SyncResource("new", events)))
    frame = _frame({"resource": "make()"}, make=lambda: next(resources))
    await frame.get("resource")
    await frame.recalculate("resource")
    await frame.close()
    assert events == ["new", "old"]
