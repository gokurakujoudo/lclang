"""Inherited workflow context resources and complete exceptional cleanup."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import cast

import pytest

import lclang
import lclang.workflow as wf


@dataclass
class Value:
    """One mapped resource or result."""

    value: int


def execution_context(frame: lclang.Frame) -> wf.WorkflowExecutionContext:
    """Supply deterministic metadata with verbose in-memory logs."""
    return wf.WorkflowExecutionContext(
        False,
        date(2026, 9, 22),
        True,
        logging.getLogger("resource-scope"),
        frame,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("outside", [False, True])
async def test_resources_follow_subtree_scope_and_cli_visibility(
    outside: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Descendants inherit masked resources; outside siblings retain external values."""
    resource = wf.define_variable[int]("resource")
    published = wf.define_variable[int]("published")
    observed: list[int] = []
    events: list[str] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        context.frame.mixin({"resource!": args.value})
        try:
            yield args
        finally:
            events.append("exit")

    async def action(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        observed.append(args.value)
        events.append(str(context.task_node.task_id))
        return args

    leaf = wf.define_task(
        "leaf",
        "Leaf",
        task_action=action,
        args_mapping=Value(resource.quote),
        outputs_mapping=Value(published.quote),
    )
    branch = wf.define_task(
        "branch",
        "Branch",
        children=[
            wf.define_task(
                "middle",
                "Middle",
                children=[leaf],
            )
        ],
        context_tasks=[
            wf.define_context_task(
                "scope",
                "Resource",
                scope,
                Value(314159),
                Value(resource.quote),
            )
        ],
    )
    siblings = [branch]
    if outside:
        siblings.append(
            wf.define_task(
                "outside", "Outside", task_action=action, args_mapping=Value(resource.quote)
            )
        )
    workflow = wf.define_workflow("Resources", wf.define_task("root", "Root", children=siblings))
    assert [item.name for item in workflow.to_cli("run", "Run").parameter_docs] == (
        ["resource"] if outside else []
    )
    async with lclang.define_frame(preset={"resource": 9}) as frame:
        with caplog.at_level(logging.DEBUG, logger="resource-scope"):
            result = await workflow.execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert await frame.get("resource") == 9
        assert await frame.get("published") == 314159
    assert observed == ([314159, 9] if outside else [314159])
    assert events[:3] == ["enter", "leaf", "exit"]
    args_log = next(
        message
        for message in caplog.messages
        if message.startswith(
            "args mapping: [root.branch.middle.leaf]",
        )
    )
    assert "*masked*" in args_log and "314159" not in args_log


def exception_leaves(error: BaseException) -> list[BaseException]:
    """Flatten grouped failures while retaining their original instances."""
    if isinstance(error, BaseExceptionGroup):
        return [
            leaf
            for child in cast(BaseExceptionGroup[BaseException], error).exceptions
            for leaf in exception_leaves(child)
        ]
    return [error]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_business_and_multiple_cleanup_failures_are_retained(cancel: bool) -> None:
    """Ordinary errors group; cancellation propagates with all cleanup causes."""
    events: list[int] = []
    business = asyncio.CancelledError("cancel") if cancel else ValueError("business")
    failures = [RuntimeError("outer"), RuntimeError("inner")]

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        finally:
            events.append(args.value)
            raise failures[args.value]

    async def fail(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        raise business

    root = wf.define_task(
        "root",
        "Root",
        task_action=fail,
        args_mapping=Value(0),
        context_tasks=[
            wf.define_context_task("outer", "Outer", scope, Value(0)),
            wf.define_context_task("inner", "Inner", scope, Value(1)),
        ],
    )
    async with lclang.define_frame() as frame:
        workflow = wf.define_workflow("Failures", root)
        if cancel:
            with pytest.raises(asyncio.CancelledError) as caught:
                await workflow.execute(execution_context(frame))
            assert caught.value is business
            assert caught.value.__cause__ is not None
            assert set(exception_leaves(caught.value.__cause__)) == set(failures)
        else:
            result = await workflow.execute(execution_context(frame))
            assert result.execution_status.status is wf.ExecutionStatus.ERROR
            failure = cast(wf.WorkflowException, await frame.get("__exception__"))
            assert set(exception_leaves(failure.exception)) == {business, *failures}
    assert events == [1, 0]


@pytest.mark.asyncio
@pytest.mark.parametrize("pending_kind", ["ordinary", "cancel", "none"])
async def test_task_frame_close_keeps_prior_failure(
    pending_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Frame close failure cannot replace an action failure or cancellation."""
    prior: Exception | asyncio.CancelledError | None = (
        ValueError("action")
        if pending_kind == "ordinary"
        else asyncio.CancelledError() if pending_kind == "cancel" else None
    )
    cleanup = RuntimeError("frame close")
    original = lclang.Frame.close

    async def close(frame: lclang.Frame) -> None:
        await original(frame)
        if str(frame.frame_id) == "root":
            raise cleanup

    async def action(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        if prior is not None:
            raise prior
        return args

    monkeypatch.setattr(lclang.Frame, "close", close)
    workflow = wf.define_workflow(
        "Close",
        wf.define_task(
            "root",
            "Root",
            task_action=action,
            args_mapping=Value(1),
        ),
    )
    async with lclang.define_frame() as frame:
        if pending_kind == "cancel":
            with pytest.raises(asyncio.CancelledError) as caught:
                await workflow.execute(execution_context(frame))
            assert caught.value is prior and caught.value.__cause__ is cleanup
        else:
            result = await workflow.execute(execution_context(frame))
            assert result.execution_status.status is wf.ExecutionStatus.ERROR
            failure = cast(wf.WorkflowException, await frame.get("__exception__"))
            assert set(exception_leaves(failure.exception)) == (
                {prior, cleanup} if prior is not None else {cleanup}
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("during", ["enter", "exit", "close"])
async def test_cancellation_at_lifecycle_boundaries_unwinds_outer_resources(
    during: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Process control at each lifecycle boundary remains visible to the caller."""
    exited: list[str] = []
    cancellation = asyncio.CancelledError("lifecycle")
    ordinary = ValueError("business")
    original = lclang.Frame.close

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        if args.value == 1 and during == "enter":
            raise cancellation
        try:
            yield args
        finally:
            exited.append(str(args.value))
            if args.value == 1 and during == "exit":
                raise cancellation

    async def close(frame: lclang.Frame) -> None:
        await original(frame)
        if str(frame.frame_id) == "root" and during == "close":
            raise cancellation

    async def fail(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        raise ordinary

    monkeypatch.setattr(lclang.Frame, "close", close)
    task = wf.define_task(
        "root",
        "Root",
        task_action=fail,
        args_mapping=Value(0),
        context_tasks=[
            wf.define_context_task("outer", "Outer", scope, Value(0)),
            wf.define_context_task("inner", "Inner", scope, Value(1)),
        ],
    )
    async with lclang.define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Cancel", task).execute(execution_context(frame))
    assert caught.value is cancellation
    assert exited == (["0"] if during == "enter" else ["1", "0"])
    if during != "enter":
        assert cancellation.__cause__ is ordinary


@pytest.mark.asyncio
async def test_reraised_original_failure_is_not_duplicated() -> None:
    """A context reraising the same exception preserves its identity."""
    from lclang.workflow.failures import combine_failures

    error = ValueError("original")
    assert combine_failures(error, error) is error
