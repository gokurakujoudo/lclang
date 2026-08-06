"""Unit tests mirroring :mod:`pylcl.lang.evaluator.contexts`."""

import asyncio

import pytest

from pylcl import evaluate
from pylcl.errors import LclEvaluationError
from pylcl.lang.parser import parse_expression
from tests.lang.evaluator.context_support import AsyncManager, SyncManager


@pytest.mark.asyncio
async def test_sync_manager_binds_body_value_without_mutating_caller() -> None:
    """A sync enter result is local to the with body."""
    events: list[str] = []
    values: dict[str, object] = {
        "resource": SyncManager("resource", events, value=42),
        "item": "outer",
    }
    source = "with resource as item: item"
    assert await evaluate(parse_expression(source), values) == 42
    assert values["item"] == "outer"
    assert events == ["enter resource", "exit resource"]


@pytest.mark.asyncio
async def test_async_protocol_is_preferred_and_awaited() -> None:
    """A complete async protocol takes precedence over sync methods."""
    events: list[str] = []
    manager = AsyncManager(events, "ready")
    node = parse_expression("with manager as value: value")
    assert await evaluate(node, {"manager": manager}) == "ready"
    assert events == ["async enter", "async exit"]


@pytest.mark.asyncio
async def test_later_context_resolves_earlier_binding() -> None:
    """Context items acquire left-to-right through progressively nested scope."""
    events: list[str] = []
    first = SyncManager("first", events, value=3)

    def make(value: object) -> SyncManager:
        return SyncManager("second", events, value=int(str(value)) + 1)

    source = "with first as value, make(value) as next_value: next_value"
    assert await evaluate(parse_expression(source), {"first": first, "make": make}) == 4
    assert events == ["enter first", "enter second", "exit second", "exit first"]


@pytest.mark.asyncio
async def test_later_entry_failure_unwinds_earlier_manager() -> None:
    """An acquired manager exits when the next manager cannot enter."""
    events: list[str] = []
    first = SyncManager("first", events)
    second = SyncManager("second", events, enter_error=ValueError("no entry"))
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("with first, second: None"), locals())
    assert isinstance(caught.value.__cause__, ValueError)
    assert first.seen_error is second.enter_error
    assert events == ["enter first", "enter second", "exit first"]


@pytest.mark.asyncio
async def test_truthy_exit_suppresses_body_failure() -> None:
    """A suppressing exit converts the failed with expression to ``None``."""
    events: list[str] = []
    manager = SyncManager("manager", events, suppress=True)

    def fail() -> None:
        raise ValueError("suppressed")

    source = "with manager: fail()"
    assert await evaluate(parse_expression(source), locals()) is None
    assert isinstance(manager.seen_error, LclEvaluationError)


@pytest.mark.asyncio
async def test_falsey_exit_preserves_wrapped_body_failure() -> None:
    """A non-suppressing manager receives and propagates the body failure."""
    events: list[str] = []
    manager = SyncManager("manager", events)

    def fail() -> None:
        raise ValueError("visible")

    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("with manager: fail()"), locals())
    assert manager.seen_error is caught.value
    assert isinstance(caught.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_exit_failure_replaces_successful_body_result() -> None:
    """A cleanup error becomes the source-aware with-node failure."""
    events: list[str] = []
    manager = SyncManager("manager", events, exit_error=RuntimeError("cleanup"))
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("with manager: 42"), locals())
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_sync_protocol_results_are_auto_awaited() -> None:
    """Awaitables returned from nominal sync methods are fully resolved."""
    events: list[str] = []

    class AwaitingManager:
        def __enter__(self) -> object:
            async def entered() -> str:
                events.append("entered")
                return "value"

            return entered()

        def __exit__(self, *details: object) -> object:
            del details

            async def exited() -> bool:
                events.append("exited")
                return False

            return exited()

    manager = AwaitingManager()
    source = "with manager as value: value"
    assert await evaluate(parse_expression(source), locals()) == "value"
    assert events == ["entered", "exited"]


@pytest.mark.asyncio
async def test_cancellation_unwinds_and_is_not_wrapped() -> None:
    """Cancellation reaches exits and then remains a direct base exception."""
    events: list[str] = []
    manager = SyncManager("manager", events)

    async def cancel() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await evaluate(parse_expression("with manager: cancel()"), locals())
    assert isinstance(manager.seen_error, asyncio.CancelledError)
    assert events == ["enter manager", "exit manager"]
