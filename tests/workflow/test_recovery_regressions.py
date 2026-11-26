"""Workflow recovery preserves status evidence while allowing later tasks to run."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date

import pytest

import lclang.workflow as wf
from lclang.error import LclError, LclWorkflowError
from lclang.lang import define_frame
from lclang.lang.runtime import Frame
from tests.workflow.call_support import Value, install_call_resource, make_child, run_parent


def execution_context(frame: Frame) -> wf.WorkflowExecutionContext:
    """Build deterministic metadata for a real workflow execution."""
    return wf.WorkflowExecutionContext(
        False, date(2026, 1, 1), False, logging.getLogger("recovery-regressions"), frame
    )


@pytest.mark.asyncio
async def test_covering_context_runs_outer_sibling_and_records_interrupted_children() -> None:
    """The recovered subtree stops internally, but its outer sibling runs after cleanup."""
    events: list[str] = []

    @asynccontextmanager
    async def cover(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        try:
            yield args
        except LclWorkflowError as error:
            assert isinstance(error.__cause__, ValueError)
            events.append("handled")
            status_mgr.update(wf.ExecutionStatus.FAILURE_COVERED)
        finally:
            events.append("cleanup")

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("failed")
        raise ValueError("business failure")

    async def next_action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("sibling")
        return args

    failed = wf.define_task(
        "failed",
        "Failed task",
        task_action=fail,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("cover", "Cover", cover, Value(1))],
        children=[wf.define_task("interrupted", "Interrupted")],
    )
    sibling = wf.define_task("sibling", "Sibling", task_action=next_action, args_mapping=Value(2))
    workflow = wf.define_workflow(
        "Recovery", wf.define_task("root", "Root", children=[failed, sibling])
    )

    async with define_frame() as frame:
        result = await workflow.execute(execution_context(frame))

    root = result.execution_status.sub_tasks[0]
    failed_status, sibling_status = root.sub_tasks
    assert events == ["enter", "failed", "handled", "cleanup", "sibling"]
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE_COVERED
    assert failed_status.status is wf.ExecutionStatus.FAILURE_COVERED
    assert failed_status.sub_tasks[0].status is wf.ExecutionStatus.FAILURE_COVERED
    assert failed_status.sub_tasks[-1].task_name == "interrupted"
    assert failed_status.sub_tasks[-1].status is wf.ExecutionStatus.SKIPPED
    assert sibling_status.status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_dynamic_covered_status_is_visible_in_result_and_next_child_runs() -> None:
    """A dynamic covered result is retained without turning the parent into FAILURE."""
    observed: list[wf.ExecutionStatus] = []

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child(wf.ExecutionStatus.FAILURE_COVERED).execute_in_task(
            context, manager, name="call", preset={"input": 3}
        ) as child_result:
            observed.append(child_result.execution_status.status)
        observed.append(manager.current.status)
        return Value(1)

    async with define_frame() as frame:
        result = await run_parent(parent, frame, [wf.define_task("after", "After")])

    parent_status = result.execution_status.sub_tasks[0]
    assert observed == [wf.ExecutionStatus.FAILURE_COVERED, wf.ExecutionStatus.RUNNING]
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE_COVERED
    assert parent_status.sub_tasks[0].task_name == "parent$action"
    assert parent_status.sub_tasks[0].status is wf.ExecutionStatus.FAILURE_COVERED
    assert parent_status.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.FAILURE_COVERED
    assert parent_status.sub_tasks[1].status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_explicit_success_after_dynamic_error_survives_ancestor_finalization() -> None:
    """An action can handle an error while retaining its failed child as evidence."""
    observed: list[wf.ExecutionStatus] = []

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child(wf.ExecutionStatus.ERROR).execute_in_task(
            context, manager, name="call", preset={"input": 3}
        ) as child_result:
            observed.append(child_result.execution_status.status)
        observed.append(manager.current.status)
        manager.update(wf.ExecutionStatus.SUCCESS, "handled child error")
        return Value(1)

    async with define_frame() as frame:
        result = await run_parent(parent, frame, [wf.define_task("after", "After")])

    parent_status = result.execution_status.sub_tasks[0]
    assert observed == [wf.ExecutionStatus.ERROR, wf.ExecutionStatus.RUNNING]
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert parent_status.status is wf.ExecutionStatus.SUCCESS
    action_status = parent_status.sub_tasks[0]
    assert action_status.task_name == "parent$action"
    assert action_status.status is wf.ExecutionStatus.SUCCESS
    assert action_status.task_description == "handled child error"
    assert action_status.sub_tasks[0].status is wf.ExecutionStatus.ERROR
    assert parent_status.sub_tasks[1].status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
@pytest.mark.parametrize("action_result", ["step", "covered"])
async def test_later_child_error_overrides_automatically_aggregated_action_result(
    action_result: str,
) -> None:
    """An action's successful or covered child cannot mask a later new failure."""
    observed: list[wf.ExecutionStatus] = []

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        if action_result == "step":
            manager.add_step("prepared", "Prepared", wf.ExecutionStatus.SUCCESS)
        else:
            async with make_child(wf.ExecutionStatus.FAILURE_COVERED).execute_in_task(
                context, manager, name="call", preset={"input": 3}
            ) as child_result:
                observed.append(child_result.execution_status.status)
        return Value(1)

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(wf.ExecutionStatus.ERROR, "new error")
        return args

    broken = wf.define_task("broken", "Broken", task_action=fail, args_mapping=Value(1))
    after = wf.define_task("after", "After")
    async with define_frame() as frame:
        result = await run_parent(parent, frame, [broken, after])

    parent_status = result.execution_status.sub_tasks[0]
    assert observed == ([wf.ExecutionStatus.FAILURE_COVERED] if action_result == "covered" else [])
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert parent_status.status is wf.ExecutionStatus.ERROR
    assert parent_status.sub_tasks[-2].status is wf.ExecutionStatus.ERROR
    assert parent_status.sub_tasks[-1].status is wf.ExecutionStatus.SKIPPED


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [wf.ExecutionStatus.FAILURE, wf.ExecutionStatus.ERROR])
@pytest.mark.parametrize("handled_history", [False, True])
async def test_later_failure_is_not_hidden_by_explicit_action_success(
    status: wf.ExecutionStatus, handled_history: bool
) -> None:
    """An explicit action outcome cannot suppress a failure from a later declared child."""

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        if handled_history:
            async with make_child(wf.ExecutionStatus.ERROR).execute_in_task(
                context, manager, name="handled", preset={"input": 3}
            ) as child_result:
                assert child_result.execution_status.status is wf.ExecutionStatus.ERROR
        manager.update(wf.ExecutionStatus.SUCCESS, "action succeeded")
        return Value(1)

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        status_mgr.update(status, "later failure")
        return args

    broken = wf.define_task("broken", "Broken", task_action=fail, args_mapping=Value(1))
    async with define_frame() as frame:
        result = await run_parent(parent, frame, [broken, wf.define_task("after", "After")])

    root = result.execution_status.sub_tasks[0]
    assert result.execution_status.status is status
    assert root.status is status
    assert root.sub_tasks[-2].status is status
    assert root.sub_tasks[-1].status is wf.ExecutionStatus.SKIPPED
    if handled_history:
        assert root.sub_tasks[0].task_name == "parent$action"
        assert root.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["setup", "body", "cleanup"])
async def test_action_can_explicitly_handle_dynamic_scope_exception(
    stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caught call exception remains visible below an explicitly successful action."""
    failure = OSError(f"{stage} failure")

    class Resource:
        def close(self) -> None:
            if stage == "cleanup":
                raise failure

    if stage == "setup":

        def fail_setup() -> Frame:
            raise failure

        monkeypatch.setattr("lclang.workflow.workflow_call.define_frame", fail_setup)
    else:
        install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        with pytest.raises(LclError) as caught:
            async with make_child().execute_in_task(
                context, manager, name="call", preset={"input": 3}
            ) as child_result:
                assert isinstance(await child_result.execution_frame.get("resource"), Resource)
                if stage == "body":
                    raise failure
        assert caught.value.__cause__ is failure
        manager.update(wf.ExecutionStatus.SUCCESS, "handled call failure")
        return Value(1)

    async with define_frame() as frame:
        result = await run_parent(parent, frame, [wf.define_task("after", "After")])

    root = result.execution_status.sub_tasks[0]
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert root.status is wf.ExecutionStatus.SUCCESS
    assert root.sub_tasks[0].task_name == "parent$action"
    assert root.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.ERROR
    assert root.sub_tasks[1].status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_context_exit_failure_overrides_explicit_action_success() -> None:
    """A new cleanup error fails the task even after its action reports success."""
    events: list[str] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        yield args
        events.append("exit")
        raise ValueError("exit failed")

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("action")
        status_mgr.update(wf.ExecutionStatus.SUCCESS)
        return args

    task = wf.define_task(
        "task",
        "Task",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("scope", "Scope", scope, Value(1))],
    )
    sibling = wf.define_task("sibling", "Sibling")
    workflow = wf.define_workflow(
        "Cleanup", wf.define_task("root", "Root", children=[task, sibling])
    )
    async with define_frame() as frame:
        result = await workflow.execute(execution_context(frame))

    root = result.execution_status.sub_tasks[0]
    assert events == ["enter", "action", "exit"]
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert root.sub_tasks[0].status is wf.ExecutionStatus.ERROR
    assert root.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.ERROR
    assert root.sub_tasks[1].status is wf.ExecutionStatus.SKIPPED


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_success", [False, True])
async def test_unfinished_step_stops_later_sibling(explicit_success: bool) -> None:
    """An unfinished step fails its task when finalized and stops later siblings."""
    events: list[str] = []

    async def parent_action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        if explicit_success:
            status_mgr.update(wf.ExecutionStatus.SUCCESS, "parent action finished")
        return args

    async def child_action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("child")
        status_mgr.add_step("unfinished", "Started")
        return args

    async def sibling_action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("sibling")
        return args

    child = wf.define_task("child", "Child", task_action=child_action, args_mapping=Value(1))
    sibling = wf.define_task(
        "sibling", "Sibling", task_action=sibling_action, args_mapping=Value(2)
    )
    parent = wf.define_task(
        "parent",
        "Parent",
        task_action=parent_action,
        args_mapping=Value(0),
        children=[child, sibling],
    )
    async with define_frame() as frame:
        result = await wf.define_workflow("Unfinished", parent).execute(execution_context(frame))

    parent_status = result.execution_status.sub_tasks[0]
    action_status, child_status, sibling_status = parent_status.sub_tasks
    assert action_status.task_name == "parent$action"
    step = child_status.sub_tasks[0].sub_tasks[0]
    assert events == ["child"]
    assert result.execution_status.status is wf.ExecutionStatus.FAILURE
    assert parent_status.status is wf.ExecutionStatus.FAILURE
    assert child_status.status is wf.ExecutionStatus.FAILURE
    assert step.status is wf.ExecutionStatus.FAILURE
    assert step.task_description == "Started (did not finish)"
    assert sibling_status.status is wf.ExecutionStatus.SKIPPED
