"""Failure-covering hooks retain business, handling and release failures."""

import asyncio
from dataclasses import dataclass
from typing import cast

import pytest

from lclang.error import LclError, LclErrorGroup
from lclang.error.failure_aggregation import combine_failures
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    FailureCoveringContextTask,
    TaskContext,
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
