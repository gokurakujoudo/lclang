"""Tree workflow execution contracts."""

from __future__ import annotations

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
class NumberArgs:
    """One numeric task input."""

    value: int


@dataclass
class ResourceArgs:
    """Arguments combining an external value and a local resource."""

    value: int
    resource: int


@dataclass
class NumberOutputs:
    """One numeric task output."""

    value: int


@dataclass
class DoubleOutputs:
    """Two output fields used for duplicate-publication failures."""

    first: int
    second: int


def execution_context(frame: lclang.Frame) -> wf.WorkflowExecutionContext:
    """Return one deterministic workflow execution context.

    :param frame: Shared execution Frame.
    :returns: Context using stable test metadata.
    """
    return wf.WorkflowExecutionContext(
        is_dryrun=False,
        as_of_date=date(2026, 8, 27),
        verbose_mode=False,
        logger=logging.getLogger("workflow-test"),
        frame=frame,
    )


@pytest.mark.asyncio
async def test_nested_siblings_publish_outputs_and_scope_context_resources() -> None:
    """Sunny composite execution is parent-first DFS over inherited task Frames."""
    events: list[str] = []
    source = wf.define_variable[int]("source", "External source")
    resource = wf.define_variable[int]("resource")
    parent_value = wf.define_variable[int]("parent_value")
    child_value = wf.define_variable[int]("child_value")

    @asynccontextmanager
    async def use_resource(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[NumberOutputs]:
        """Provide one task-local resource.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context status manager.
        :returns: Async iterator yielding the resource output.
        """
        del context, status_mgr
        events.append("context-enter")
        try:
            yield NumberOutputs(args.value * 10)
        finally:
            events.append("context-exit")

    async def parent_action(
        context: wf.TaskContext,
        args: ResourceArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Combine external and task-local values.

        :param context: Current task context.
        :param args: Materialized action arguments.
        :param status_mgr: Current task status manager.
        :returns: Published parent output.
        """
        del status_mgr
        events.append("parent")
        assert context.task_id_stack == [wf.TaskID("root")]
        return NumberOutputs(args.value + args.resource)

    async def child_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Publish a child result while inheriting the parent's context resource.

        :param context: Current task context.
        :param args: Materialized action arguments.
        :param status_mgr: Current task status manager.
        :returns: Published child output.
        """
        del status_mgr
        events.append("child")
        assert context.frame.has("resource") is True
        assert context.task_id_stack == [wf.TaskID("root"), wf.TaskID("child")]
        return NumberOutputs(args.value + 1)

    async def sibling_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Consume the earlier sibling's published output.

        :param context: Current task context.
        :param args: Materialized action arguments.
        :param status_mgr: Current task status manager.
        :returns: Unpublished output.
        """
        del context, status_mgr
        events.append("sibling")
        return NumberOutputs(args.value + 1)

    context_task = wf.define_context_task(
        "resource_context",
        "Provide resource",
        use_resource,
        NumberArgs(source.quote),
        NumberOutputs(resource.quote),
    )
    child = wf.define_task(
        "child",
        "First child",
        task_action=child_action,
        args_mapping=NumberArgs(parent_value.quote),
        outputs_mapping=NumberOutputs(child_value.quote),
    )
    sibling = wf.define_task(
        "sibling",
        "Second child",
        task_action=sibling_action,
        args_mapping=NumberArgs(child_value.quote),
    )
    root = wf.define_task(
        "root",
        "Root",
        task_action=parent_action,
        args_mapping=ResourceArgs(source.quote, resource.quote),
        outputs_mapping=NumberOutputs(parent_value.quote),
        context_tasks=[context_task],
        children=[child, sibling],
    )

    async with lclang.define_frame(preset={"source": 2}) as frame:
        result = await wf.define_workflow("Composite", root).execute(execution_context(frame))
        assert events == [
            "context-enter",
            "parent",
            "child",
            "sibling",
            "context-exit",
        ]
        assert await frame.get("parent_value") == 22
        assert await frame.get("child_value") == 23
        assert result.execution_frame is frame
        assert result.task_args[wf.TaskID("root")] == ResourceArgs(2, 20)
        assert result.task_outputs[wf.TaskID("sibling")] == NumberOutputs(24)
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_unhandled_action_error_records_failure_and_skips_full_branch() -> None:
    """Rainy execution records the origin and materializes skipped descendants."""
    source = wf.define_variable[int]("source")

    async def fail_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Raise one action failure.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: No output because execution fails.
        :raises ValueError: Always.
        """
        del context, args, status_mgr
        raise ValueError("broken action")

    @asynccontextmanager
    async def skipped_context(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[NumberOutputs]:
        """Define a context that must be materialized as skipped.

        :param context: Current task context.
        :param args: Context arguments.
        :param status_mgr: Context status manager.
        :returns: Iterator that would yield one output.
        """
        del context, status_mgr
        yield NumberOutputs(args.value)

    skipped = wf.define_context_task(
        "skipped_context", "Skipped context", skipped_context, NumberArgs(source.quote)
    )
    grandchild = wf.define_task("grandchild", "Grandchild")
    child = wf.define_task("child", "Child", context_tasks=[skipped], children=[grandchild])
    root = wf.define_task(
        "root",
        "Root",
        task_action=fail_action,
        args_mapping=NumberArgs(source.quote),
        children=[child],
    )
    async with lclang.define_frame(preset={"source": 1}) as frame:
        result = await wf.define_workflow("Rainy", root).execute(execution_context(frame))
        failure = await frame.get("__exception__")

    assert isinstance(failure, wf.WorkflowException)
    assert isinstance(failure.exception, ValueError)
    assert failure.error_task == wf.TaskID("root")
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    task = result.execution_status.sub_tasks[0]
    assert task.sub_tasks[0].status is wf.ExecutionStatus.SKIPPED
    assert task.sub_tasks[0].sub_tasks[0].task_name == "skipped_context"
    assert task.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.SKIPPED
    assert task.sub_tasks[0].sub_tasks[1].status is wf.ExecutionStatus.SKIPPED
    assert wf.TaskID("root") in result.task_args
    assert wf.TaskID("root") not in result.task_outputs


class CoverFailure(wf.FailureCoveringContextTask[NumberArgs, NumberOutputs]):
    """Cover one inner exception and record housekeeping events."""

    def __init__(self, events: list[str]) -> None:
        """Retain the event collector.

        :param events: Mutable execution event collector.
        """
        self.events = events

    async def acquire(
        self,
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Acquire one synthetic resource.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context status manager.
        :returns: Synthetic resource.
        """
        del context, status_mgr
        self.events.append("acquire")
        return NumberOutputs(args.value)

    async def handle_exception(
        self,
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
        resource: NumberOutputs,
        exception: Exception,
    ) -> None:
        """Confirm the expected inner exception.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context status manager.
        :param resource: Acquired resource.
        :param exception: Inner exception.
        """
        del context, args, status_mgr, resource
        assert str(exception) == "covered"
        self.events.append("handle")

    async def release(
        self,
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
        resource: NumberOutputs,
    ) -> None:
        """Record deterministic cleanup.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context status manager.
        :param resource: Acquired resource.
        """
        del context, args, status_mgr, resource
        self.events.append("release")


@pytest.mark.asyncio
async def test_covering_context_wraps_failure_but_still_skips_sibling() -> None:
    """Covered failure performs housekeeping, remains visible, and stops DFS."""
    events: list[str] = []
    source = wf.define_variable[int]("source")

    async def fail_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Raise the covered error.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: No output.
        :raises ValueError: Always.
        """
        del context, args, status_mgr
        raise ValueError("covered")

    async def unreachable_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Record an invocation that must be skipped.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Echoed value.
        """
        del context, status_mgr
        events.append("unreachable")
        return NumberOutputs(args.value)

    covering = wf.define_context_task(
        "cover",
        "Cover failure",
        CoverFailure(events),
        NumberArgs(source.quote),
    )
    failed = wf.define_task(
        "failed",
        "Failed child",
        task_action=fail_action,
        args_mapping=NumberArgs(source.quote),
        context_tasks=[covering],
    )
    sibling = wf.define_task(
        "sibling",
        "Skipped sibling",
        task_action=unreachable_action,
        args_mapping=NumberArgs(source.quote),
    )
    root = wf.define_task("root", "Root", children=[failed, sibling])

    async with lclang.define_frame(preset={"source": 3}) as frame:
        result = await wf.define_workflow("Covered", root).execute(execution_context(frame))

    assert events == ["acquire", "handle", "release"]
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE_COVERED
    root_status = result.execution_status.sub_tasks[0]
    assert root_status.sub_tasks[0].status is wf.ExecutionStatus.FAILURE_COVERED
    assert root_status.sub_tasks[1].status is wf.ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_explicit_failure_creates_synthetic_exception_and_stops() -> None:
    """A status-only failure has a concrete exception and skips descendants."""
    source = wf.define_variable[int]("source")

    async def reject_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        """Set one expected failure status.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Returned value retained before the stop.
        """
        del context
        status_mgr.update(wf.ExecutionStatus.FAILURE, "rejected")
        return NumberOutputs(args.value)

    root = wf.define_task(
        "root",
        "Root",
        task_action=reject_action,
        args_mapping=NumberArgs(source.quote),
        children=[wf.define_task("child", "Skipped")],
    )
    async with lclang.define_frame(preset={"source": 4}) as frame:
        result = await wf.define_workflow("Rejected", root).execute(execution_context(frame))
        failure = await frame.get("__exception__")

    assert result.execution_status.status is wf.ExecutionStatus.FAILURE
    assert result.task_outputs[wf.TaskID("root")] == NumberOutputs(4)
    assert result.execution_status.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.SKIPPED
    assert isinstance(cast(wf.WorkflowException, failure).exception, RuntimeError)


@pytest.mark.asyncio
async def test_context_enter_exit_and_unsuppressed_failures_are_recorded() -> None:
    """Every async context boundary records its own ordinary failure origin."""
    source = wf.define_variable[int]("source")

    @asynccontextmanager
    async def fail_enter(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[NumberOutputs]:
        del context, args, status_mgr
        raise ValueError("enter failed")
        yield NumberOutputs(0)  # type: ignore[unreachable]

    @asynccontextmanager
    async def fail_exit(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[NumberOutputs]:
        del context, status_mgr
        try:
            yield NumberOutputs(args.value)
        finally:
            raise ValueError("exit failed")

    @asynccontextmanager
    async def pass_through(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[NumberOutputs]:
        del context, status_mgr
        yield NumberOutputs(args.value)

    async def fail_action(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        del context, args, status_mgr
        raise ValueError("inner failed")

    definitions = (
        ("enter", fail_enter, None, "enter failed"),
        ("exit", fail_exit, None, "exit failed"),
        ("inner", pass_through, fail_action, "inner failed"),
    )
    for identifier, context_factory, action, message in definitions:
        context_task = wf.define_context_task(
            f"{identifier}_context",
            "Context",
            context_factory,
            NumberArgs(source.quote),
        )
        context_tasks = [context_task]
        if identifier == "enter":
            context_tasks.append(
                wf.define_context_task(
                    "later_context",
                    "Later context",
                    pass_through,
                    NumberArgs(source.quote),
                )
            )
        task = wf.define_task(
            f"{identifier}_task",
            "Task",
            task_action=action,
            args_mapping=None if action is None else NumberArgs(source.quote),
            context_tasks=context_tasks,
        )
        async with lclang.define_frame(preset={"source": 1}) as frame:
            result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))
            failure = cast(wf.WorkflowException, await frame.get("__exception__"))
        assert str(failure.exception) == message
        assert result.execution_status.status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_wrong_action_outputs_and_duplicate_publication_fail_cleanly() -> None:
    """Runtime output contracts become task errors with retained arguments."""
    source = wf.define_variable[int]("source")
    target = wf.define_variable[int]("target")

    async def wrong_output(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> NumberOutputs:
        del context, args, status_mgr
        return cast(NumberOutputs, 1)

    async def duplicate_output(
        context: wf.TaskContext,
        args: NumberArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> DoubleOutputs:
        del context, status_mgr
        return DoubleOutputs(args.value, args.value + 1)

    tasks = (
        wf.define_task(
            "wrong",
            "Wrong",
            task_action=wrong_output,
            args_mapping=NumberArgs(source.quote),
        ),
        wf.define_task(
            "duplicate",
            "Duplicate",
            task_action=duplicate_output,
            args_mapping=NumberArgs(source.quote),
            outputs_mapping=DoubleOutputs(target.quote, target.quote),
        ),
    )
    for task in tasks:
        async with lclang.define_frame(preset={"source": 1}) as frame:
            result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))
            failure = cast(wf.WorkflowException, await frame.get("__exception__"))
        assert isinstance(failure.exception, (TypeError, ValueError))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_defensive_execution_validation_and_task_frame_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupted definitions and cleanup errors still produce concrete failures."""
    with pytest.raises(TypeError, match="execution context"):
        await wf.define_workflow("Workflow", wf.define_task("root", "Root")).execute(
            cast(wf.WorkflowExecutionContext, object())
        )

    invalid = wf.TaskNode(
        wf.TaskID("invalid"),
        "Invalid",
        valid_action_for_corruption,
        None,
        None,
        (),
        (),
    )
    async with lclang.define_frame() as frame:
        result = await wf.Workflow("Workflow", invalid).execute(execution_context(frame))
        failure = cast(wf.WorkflowException, await frame.get("__exception__"))
    assert isinstance(failure.exception, RuntimeError)

    original_close = lclang.Frame.close

    async def selective_close(frame: lclang.Frame) -> None:
        if str(frame.frame_id) == "invalid":
            raise ValueError("close failed")
        await original_close(frame)

    monkeypatch.setattr(lclang.Frame, "close", selective_close)
    structural = wf.TaskNode(wf.TaskID("invalid"), "Invalid", None, None, None, (), ())
    async with lclang.define_frame() as frame:
        result = await wf.Workflow("Workflow", structural).execute(execution_context(frame))
        failure = cast(wf.WorkflowException, await frame.get("__exception__"))
    assert str(failure.exception) == "close failed"
    assert result.execution_status.status is wf.ExecutionStatus.ERROR


async def valid_action_for_corruption(
    context: wf.TaskContext,
    args: NumberArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> NumberOutputs:
    """Serve a manually corrupted TaskNode fixture.

    :param context: Current task context.
    :param args: Materialized arguments.
    :param status_mgr: Current status manager.
    :returns: Echoed output.
    """
    del context, status_mgr
    return NumberOutputs(args.value)


@pytest.mark.asyncio
async def test_failure_covering_base_hooks_and_clean_scope() -> None:
    """The recovery template requires key hooks and permits optional release."""
    base = wf.FailureCoveringContextTask[NumberArgs, NumberOutputs]()
    manager = wf.ExecutionStatusManager("context")
    context = cast(wf.TaskContext, object())
    with pytest.raises(NotImplementedError):
        await base.acquire(context, NumberArgs(1), manager)
    with pytest.raises(NotImplementedError):
        await base.handle_exception(
            context,
            NumberArgs(1),
            manager,
            NumberOutputs(1),
            ValueError("broken"),
        )

    class CleanContext(wf.FailureCoveringContextTask[NumberArgs, NumberOutputs]):
        """Acquire successfully and inherit no-op release."""

        async def acquire(
            self,
            context: wf.TaskContext,
            args: NumberArgs,
            status_mgr: wf.ExecutionStatusManager,
        ) -> NumberOutputs:
            """Return a clean resource.

            :param context: Current task context.
            :param args: Context arguments.
            :param status_mgr: Context status manager.
            :returns: Echoed output.
            """
            del context, status_mgr
            return NumberOutputs(args.value)

    async with CleanContext().scope(context, NumberArgs(2), manager) as resource:
        assert resource == NumberOutputs(2)
    assert manager.current.status is wf.ExecutionStatus.PENDING
