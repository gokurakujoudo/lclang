"""Failure-covering hooks retain business, handling and release failures."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import cast

import pytest

from lclang.error import LclError, LclErrorGroup
from lclang.error.failure_aggregation import combine_failures
from lclang.lang import define_frame
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    FailureCoveringContextTask,
    TaskContext,
    WorkflowExecutionContext,
    define_context_task,
    define_task,
    define_workflow,
)


@dataclass
class Value:
    """Carry one deterministic resource value."""

    value: int


def original_leaves(error: BaseException) -> list[BaseException]:
    """Select native causes without replacing their identity."""
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in original_leaves(member)]
    if isinstance(error, LclError):
        assert error.__cause__ is not None
        return [error.__cause__]
    return [error]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "handling",
        "release",
        "handled_release",
        "both",
        "covered",
        "clean",
        "cancel",
        "interrupt",
        "acquire",
        "release_control",
    ],
)
async def test_covering_scope_retains_all_pending_failures(mode: str) -> None:
    """Release runs once, covering is explicit, and controls preserve identity."""
    business = asyncio.CancelledError("cancel") if mode == "cancel" else ValueError("business")
    handling = KeyboardInterrupt("interrupt") if mode == "interrupt" else OSError("handling")
    release = KeyboardInterrupt("release") if mode == "release_control" else RuntimeError("release")
    events: list[str] = []

    class Cover(FailureCoveringContextTask[Value, Value]):
        """Inject independent hook failures after resource acquisition."""

        async def acquire(
            self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
        ) -> Value:
            events.append("acquire")
            if mode == "acquire":
                raise OSError("acquire")
            return args

        async def handle_exception(
            self,
            context: TaskContext,
            args: Value,
            status_mgr: ExecutionStatusManager,
            resource: Value,
            exception: Exception,
        ) -> None:
            events.append("handle")
            assert exception is business
            if mode in {"handling", "both", "interrupt"}:
                raise handling

        async def release(
            self,
            context: TaskContext,
            args: Value,
            status_mgr: ExecutionStatusManager,
            resource: Value,
        ) -> None:
            events.append("release")
            if mode in {
                "release",
                "handled_release",
                "both",
                "cancel",
                "interrupt",
                "release_control",
            }:
                raise release

    manager = ExecutionStatusManager("cover")
    context = cast(TaskContext, object())
    pending: BaseException | None = None
    try:
        async with Cover().scope(context, Value(1), manager) as resource:
            assert resource == Value(1)
            if mode not in {"clean", "release"}:
                raise business
    except BaseException as error:
        pending = error
    if mode == "acquire":
        assert events == ["acquire"]
        assert isinstance(pending, LclError) and pending.code == "LCL532811"
        assert isinstance(pending.__cause__, OSError)
        return
    assert events == (
        ["acquire", "release"]
        if mode in {"clean", "release", "cancel"}
        else ["acquire", "handle", "release"]
    )
    if mode in {"clean", "covered"}:
        assert pending is None
        assert manager.current.status is (
            ExecutionStatus.FAILURE_COVERED if mode == "covered" else ExecutionStatus.PENDING
        )
    elif mode in {"release", "handled_release"}:
        assert isinstance(pending, LclError) and pending.__cause__ is release
        assert pending.code == "LCL532812"
    elif mode == "release_control":
        assert pending is not None
        assert pending is release and pending.__cause__ is None
    elif mode in {"cancel", "interrupt"}:
        assert pending is not None
        assert pending is (business if mode == "cancel" else handling)
        assert pending.__cause__ is not None
        assert original_leaves(pending.__cause__) == (
            [release] if mode == "cancel" else [business, release]
        )
    else:
        assert isinstance(pending, LclErrorGroup) and pending.code == "LCL535911"
        assert original_leaves(pending) == [business, handling] + (
            [release] if mode == "both" else []
        )


def test_outer_unwind_does_not_repeat_an_already_retained_body() -> None:
    """A covering scope's composite already contains the caller's pending body."""
    body = ValueError("business")
    handling = OSError("handling")
    release = RuntimeError("release")
    inner = combine_failures(body, handling, code="LCL535911")
    assert isinstance(inner, LclErrorGroup)
    completed = combine_failures(inner, release, code="LCL535911")
    assert combine_failures(body, completed, code="LCL535911") is completed
    assert combine_failures(completed, body, code="LCL535911") is completed
    assert original_leaves(completed) == [body, handling, release]


@pytest.mark.asyncio
@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("recover", [False, True])
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_workflow_propagates_iteration_signals_and_control_groups(
    grouped: bool, recover: bool, cleanup_fails: bool
) -> None:
    """Neither normal execution nor recovery may swallow an iterator control signal."""
    signal = StopAsyncIteration("done")
    original = ExceptionGroup("control", [signal, OSError("business")]) if grouped else signal
    cleanup = OSError("release")
    events: list[str] = []

    class Recovery(FailureCoveringContextTask[Value, Value]):
        async def acquire(
            self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
        ) -> Value:
            return args

        async def handle_exception(
            self,
            context: TaskContext,
            args: Value,
            status_mgr: ExecutionStatusManager,
            resource: Value,
            exception: Exception,
        ) -> None:
            events.append("handled")

        async def release(
            self,
            context: TaskContext,
            args: Value,
            status_mgr: ExecutionStatusManager,
            resource: Value,
        ) -> None:
            events.append("release")
            if cleanup_fails:
                raise cleanup

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        raise original

    scopes = [define_context_task("recover", "Recover", Recovery(), Value(0))] if recover else []
    task = define_task(
        "root", "Root", task_action=action, args_mapping=Value(0), context_tasks=scopes
    )
    workflow = define_workflow("Controls", task)
    async with define_frame() as frame:
        with pytest.raises(Exception) as caught:
            await workflow.execute(
                WorkflowExecutionContext(
                    False, date(2026, 1, 1), False, logging.getLogger("iterator-controls"), frame
                )
            )
        assert caught.value is original
        assert "handled" not in events
        assert events == (["release"] if recover else [])
        if recover and cleanup_fails:
            assert isinstance(original.__cause__, LclError)
            assert (
                original.__cause__.code == "LCL532812" and original.__cause__.__cause__ is cleanup
            )
        assert not frame.closed
