"""Workflow actions keep their own status beneath their containing task."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

import pytest

import lclang.workflow as wf
from lclang.error import LclWorkflowError, WorkflowException, WorkflowStatusStop
from lclang.lang import define_frame
from lclang.lang.runtime import Frame
from tests.workflow.call_support import Value, make_child


def execution_context(frame: Frame) -> wf.WorkflowExecutionContext:
    """Supply fixed metadata to a workflow execution."""
    return wf.WorkflowExecutionContext(
        False, date(2026, 1, 1), False, logging.getLogger("action-status"), frame
    )


async def echo(
    context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
) -> Value:
    """Return one value without explicitly updating action status."""
    return args


@pytest.mark.asyncio
async def test_action_has_own_status_node_and_callback_manager() -> None:
    """A clean action completes independently under its containing task."""
    observed: list[str] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        observed.append(status_mgr.current.task_name)
        status_mgr.add_step("saved", "Saved", wf.ExecutionStatus.SUCCESS)
        return args

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    action_node = next(child for child in node.sub_tasks if child.task_name == "sync$action")
    assert observed == ["sync$action"]
    assert node.status is wf.ExecutionStatus.SUCCESS
    assert action_node.task_type is wf.ExecutionTaskType.TASK
    assert action_node.task_description == "Synchronize"
    assert action_node.status is wf.ExecutionStatus.SUCCESS
    assert (
        next(child for child in action_node.sub_tasks if child.task_name == "saved").status
        is wf.ExecutionStatus.SUCCESS
    )


@pytest.mark.asyncio
async def test_explicit_action_success_does_not_hide_later_declared_failure() -> None:
    """A task aggregates a later child failure separately from its action outcome."""

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(wf.ExecutionStatus.SUCCESS, "action completed")
        return args

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(wf.ExecutionStatus.FAILURE, "declined")
        return args

    child = wf.define_task("child", "Child", task_action=fail, args_mapping=Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=action, args_mapping=Value(1), children=[child]
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    action_node = next(child for child in node.sub_tasks if child.task_name == "sync$action")
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE
    assert node.status is wf.ExecutionStatus.FAILURE
    assert action_node.status is wf.ExecutionStatus.SUCCESS
    assert action_node.task_description == "action completed"
    assert (
        next(child for child in node.sub_tasks if child.task_name == "child").status
        is wf.ExecutionStatus.FAILURE
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [wf.ExecutionStatus.FAILURE, wf.ExecutionStatus.ERROR])
async def test_context_recovers_declared_child_after_parent_action_success(
    failure: wf.ExecutionStatus,
) -> None:
    """The recovery context covers the later child while retaining action success."""
    events: list[str] = []

    @asynccontextmanager
    async def recover(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        except WorkflowStatusStop as error:
            assert failure.value in str(error)
            events.append("handled")
            status_mgr.update(wf.ExecutionStatus.FAILURE_COVERED)
        finally:
            events.append("cleanup")

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("parent")
        status_mgr.update(wf.ExecutionStatus.SUCCESS, "action succeeded")
        return args

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("child")
        status_mgr.update(failure, "declined")
        return args

    async def sibling(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("sibling")
        return args

    child = wf.define_task("child", "Child", task_action=fail, args_mapping=Value(1))
    context_task = wf.define_context_task("recover", "Recover", recover, Value(1))
    parent = wf.define_task(
        "sync",
        "Synchronize",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[context_task],
        children=[child],
    )
    later = wf.define_task("later", "Later", task_action=sibling, args_mapping=Value(1))
    root = wf.define_task("root", "Root", children=[parent, later])
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", root).execute(execution_context(frame))

    root_status = result.execution_status.sub_tasks[0]
    parent_status = next(child for child in root_status.sub_tasks if child.task_name == "sync")
    action_status = next(
        child for child in parent_status.sub_tasks if child.task_name == "sync$action"
    )
    assert events == ["parent", "child", "handled", "cleanup", "sibling"]
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE_COVERED
    assert parent_status.status is wf.ExecutionStatus.FAILURE_COVERED
    assert (
        next(child for child in parent_status.sub_tasks if child.task_name == "recover").status
        is wf.ExecutionStatus.FAILURE_COVERED
    )
    assert action_status.status is wf.ExecutionStatus.SUCCESS
    assert action_status.task_description == "action succeeded"
    assert (
        next(child for child in parent_status.sub_tasks if child.task_name == "child").status
        is failure
    )
    assert (
        next(child for child in root_status.sub_tasks if child.task_name == "later").status
        is wf.ExecutionStatus.SUCCESS
    )


@pytest.mark.asyncio
async def test_context_exit_error_leaves_action_success_visible() -> None:
    """A later context cleanup failure does not overwrite a successful action node."""
    events: list[str] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        yield args
        events.append("cleanup")
        raise ValueError("exit failed")

    context_task = wf.define_context_task("scope", "Resource", scope, Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=echo, args_mapping=Value(1), context_tasks=[context_task]
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    assert events == ["cleanup"]
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert node.status is wf.ExecutionStatus.ERROR
    assert (
        next(child for child in node.sub_tasks if child.task_name == "scope").status
        is wf.ExecutionStatus.ERROR
    )
    assert (
        next(child for child in node.sub_tasks if child.task_name == "sync$action").status
        is wf.ExecutionStatus.SUCCESS
    )


@pytest.mark.asyncio
async def test_action_explicitly_handles_dynamic_child_error() -> None:
    """A dynamic child error stays below the successful action which handled it."""

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        async with make_child(wf.ExecutionStatus.ERROR).execute_in_task(
            context, status_mgr, name="call", preset={"input": 3}
        ) as child_result:
            assert child_result.execution_status.status is wf.ExecutionStatus.ERROR
        status_mgr.update(wf.ExecutionStatus.SUCCESS, "handled")
        return args

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    action_node = next(child for child in node.sub_tasks if child.task_name == "sync$action")
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert action_node.status is wf.ExecutionStatus.SUCCESS
    assert action_node.task_description == "handled"
    assert (
        next(child for child in action_node.sub_tasks if child.task_name == "call").status
        is wf.ExecutionStatus.ERROR
    )


@pytest.mark.asyncio
async def test_explicit_action_success_precedes_dynamic_child_error() -> None:
    """An explicit action result remains authoritative over a later dynamic child result."""
    events: list[str] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(wf.ExecutionStatus.SUCCESS, "accepted")
        async with make_child(wf.ExecutionStatus.ERROR).execute_in_task(
            context, status_mgr, name="call", preset={"input": 3}
        ) as child_result:
            assert child_result.execution_status.status is wf.ExecutionStatus.ERROR
        return args

    async def after(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("after")
        return args

    child = wf.define_task("after", "After", task_action=after, args_mapping=Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=action, args_mapping=Value(1), children=[child]
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    action_node = next(child for child in node.sub_tasks if child.task_name == "sync$action")
    assert events == ["after"]
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert node.status is wf.ExecutionStatus.SUCCESS
    assert action_node.status is wf.ExecutionStatus.SUCCESS
    assert action_node.task_description == "accepted"
    assert (
        next(child for child in action_node.sub_tasks if child.task_name == "call").status
        is wf.ExecutionStatus.ERROR
    )
    assert (
        next(child for child in node.sub_tasks if child.task_name == "after").status
        is wf.ExecutionStatus.SUCCESS
    )


@dataclass
class TwoValues:
    """Two output fields for testing duplicate bindings."""

    first: int
    second: int


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["input", "output"])
async def test_mapping_failure_is_recorded_on_action(stage: str) -> None:
    """Input and output mapping errors fail the action and its task."""
    invoked: list[str] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> TwoValues:
        invoked.append("action")
        return TwoValues(args.value, args.value + 1)

    missing = wf.define_variable[int]("missing")
    target = wf.define_variable[int]("target")
    task = wf.define_task(
        "sync",
        "Synchronize",
        task_action=action,
        args_mapping=Value(missing.quote) if stage == "input" else Value(1),
        outputs_mapping=TwoValues(target.quote, target.quote) if stage == "output" else None,
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    assert invoked == ([] if stage == "input" else ["action"])
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert node.status is wf.ExecutionStatus.ERROR
    assert (
        next(child for child in node.sub_tasks if child.task_name == "sync$action").status
        is wf.ExecutionStatus.ERROR
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["input", "output"])
async def test_native_mapping_failure_preserves_code_and_cause(
    stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native mapping failures retain their classified code and original cause."""
    original = OSError(f"{stage} mapping failed")
    invoked: list[str] = []

    async def fail_mapping(*args: object, **kwargs: object) -> None:
        raise original

    operation = "materialize_args" if stage == "input" else "mapped_outputs"
    monkeypatch.setattr(f"lclang.workflow.task_execution.{operation}", fail_mapping)

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        invoked.append("action")
        return args

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))
        failure = await frame.get("__exception__")

    node = result.execution_status.sub_tasks[0]
    assert invoked == ([] if stage == "input" else ["action"])
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert node.status is wf.ExecutionStatus.ERROR
    assert (
        next(child for child in node.sub_tasks if child.task_name == "sync$action").status
        is wf.ExecutionStatus.ERROR
    )
    assert isinstance(failure, WorkflowException)
    assert isinstance(failure.exception, LclWorkflowError)
    assert failure.exception.code == "LCL522811"
    assert failure.exception.__cause__ is original


@pytest.mark.asyncio
async def test_context_enter_failure_marks_unstarted_action_skipped() -> None:
    """Failure before an action enters keeps its skipped action node in the tree."""

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        if args.value:
            raise ValueError("enter failed")
        yield args

    context_task = wf.define_context_task("scope", "Resource", scope, Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=echo, args_mapping=Value(1), context_tasks=[context_task]
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert (
        next(child for child in node.sub_tasks if child.task_name == "scope").status
        is wf.ExecutionStatus.ERROR
    )
    assert (
        next(child for child in node.sub_tasks if child.task_name == "sync$action").status
        is wf.ExecutionStatus.SKIPPED
    )


@pytest.mark.asyncio
async def test_skipped_task_retains_skipped_action_node() -> None:
    """A task skipped after an earlier failure retains its unstarted action."""

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(wf.ExecutionStatus.FAILURE)
        return args

    failed = wf.define_task("failed", "Failed", task_action=fail, args_mapping=Value(1))
    skipped = wf.define_task("sync", "Synchronize", task_action=echo, args_mapping=Value(1))
    root = wf.define_task("root", "Root", children=[failed, skipped])
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", root).execute(execution_context(frame))

    node = next(
        child
        for child in result.execution_status.sub_tasks[0].sub_tasks
        if child.task_name == "sync"
    )
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE
    assert node.status is wf.ExecutionStatus.SKIPPED
    assert (
        next(child for child in node.sub_tasks if child.task_name == "sync$action").status
        is wf.ExecutionStatus.SKIPPED
    )


@pytest.mark.asyncio
async def test_unfinished_action_step_stops_before_declared_child() -> None:
    """A still-running action step becomes failure before any declared child starts."""
    events: list[str] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.add_step("unfinished", "Started")
        return args

    async def after(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("after")
        return args

    child = wf.define_task("after", "After", task_action=after, args_mapping=Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=action, args_mapping=Value(1), children=[child]
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    node = result.execution_status.sub_tasks[0]
    action_node = next(child for child in node.sub_tasks if child.task_name == "sync$action")
    step = next(child for child in action_node.sub_tasks if child.task_name == "unfinished")
    assert not events
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE
    assert action_node.status is wf.ExecutionStatus.FAILURE
    assert step.status is wf.ExecutionStatus.FAILURE
    assert step.task_description == "Started (did not finish)"
    assert (
        next(child for child in node.sub_tasks if child.task_name == "after").status
        is wf.ExecutionStatus.SKIPPED
    )


@pytest.mark.asyncio
async def test_cancelled_action_marks_unfinished_failure_and_propagates_identity() -> None:
    """Cancellation stays native while the unfinished action is finalized as failure."""
    cancelled = asyncio.CancelledError("cancel action")
    captured: list[wf.ExecutionStatusTree] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        captured.append(status_mgr.current)
        raise cancelled

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    assert caught.value is cancelled
    assert len(captured) == 1
    assert captured[0].task_name == "sync$action"
    assert captured[0].status is wf.ExecutionStatus.FAILURE
    assert "did not finish" in captured[0].task_description


@pytest.mark.asyncio
async def test_cancelled_context_enter_keeps_unstarted_action_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation while entering a context never starts its task action."""
    cancelled = asyncio.CancelledError("cancel enter")
    captured: list[wf.ExecutionStatusTree] = []
    add_sub_task = wf.ExecutionStatusManager.add_sub_task

    def capture_sub_task(
        manager: wf.ExecutionStatusManager,
        name: str,
        description: str,
        status: wf.ExecutionStatus = wf.ExecutionStatus.PENDING,
    ) -> wf.ExecutionStatusManager:
        child = add_sub_task(manager, name, description, status)
        captured.append(child.current)
        return child

    monkeypatch.setattr(wf.ExecutionStatusManager, "add_sub_task", capture_sub_task)

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        if args.value:
            raise cancelled
        yield args

    context_task = wf.define_context_task("scope", "Resource", scope, Value(1))
    task = wf.define_task(
        "sync", "Synchronize", task_action=echo, args_mapping=Value(1), context_tasks=[context_task]
    )
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    assert caught.value is cancelled
    status_by_name = {node.task_name: node.status for node in captured}
    assert status_by_name["scope"] is wf.ExecutionStatus.FAILURE
    assert status_by_name["sync$action"] is wf.ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_cancellation_after_action_completion_preserves_action_success() -> None:
    """A cancelled context exit does not rewrite an already completed action."""
    cancelled = asyncio.CancelledError("cancel exit")
    captured: list[wf.ExecutionStatusTree] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        yield args
        raise cancelled

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        captured.append(status_mgr.current)
        return args

    context_task = wf.define_context_task("scope", "Resource", scope, Value(1))
    task = wf.define_task(
        "sync",
        "Synchronize",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[context_task],
    )
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    assert caught.value is cancelled
    assert len(captured) == 1
    assert captured[0].task_name == "sync$action"
    assert captured[0].status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_kind", ["step", "manager"])
async def test_cancelled_nested_status_scope_is_unfinished_failure(
    scope_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation of a nested scope remains cancellation, with unfinished statuses."""
    cancelled = asyncio.CancelledError("cancel nested scope")
    captured: dict[str, wf.ExecutionStatusTree] = {}
    add_sub_task = wf.ExecutionStatusManager.add_sub_task

    def capture_sub_task(
        manager: wf.ExecutionStatusManager,
        name: str,
        description: str,
        status: wf.ExecutionStatus = wf.ExecutionStatus.PENDING,
    ) -> wf.ExecutionStatusManager:
        child = add_sub_task(manager, name, description, status)
        captured[name] = child.current
        return child

    monkeypatch.setattr(wf.ExecutionStatusManager, "add_sub_task", capture_sub_task)

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        if scope_kind == "step":
            step = status_mgr.add_step("nested", "Nested")
            captured["nested"] = step.current
            with step:
                raise cancelled
        else:
            with status_mgr.add_sub_task("nested", "Nested"):
                raise cancelled

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    assert caught.value is cancelled
    for name in ("sync", "sync$action", "nested"):
        assert captured[name].status is wf.ExecutionStatus.FAILURE
        assert "did not finish" in captured[name].task_description


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_kind", ["action", "step", "manager"])
async def test_cancellation_preserves_explicit_error_in_active_scope(scope_kind: str) -> None:
    """A cancellation does not downgrade an error already set by active work."""
    cancelled = asyncio.CancelledError("cancel after error")
    captured: list[wf.ExecutionStatusTree] = []

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        if scope_kind == "action":
            status_mgr.update(wf.ExecutionStatus.ERROR, "known error")
            captured.append(status_mgr.current)
            raise cancelled
        if scope_kind == "step":
            with status_mgr.add_step("nested", "Nested") as step:
                step.update("known error", wf.ExecutionStatus.ERROR)
                captured.append(step.current)
                raise cancelled
        with status_mgr.add_sub_task("nested", "Nested") as nested:
            nested.update(wf.ExecutionStatus.ERROR, "known error")
            captured.append(nested.current)
            raise cancelled

    task = wf.define_task("sync", "Synchronize", task_action=action, args_mapping=Value(1))
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(execution_context(frame))

    assert caught.value is cancelled
    assert len(captured) == 1
    assert captured[0].status is wf.ExecutionStatus.ERROR
    assert captured[0].task_description == "known error"
