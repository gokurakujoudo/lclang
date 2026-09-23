"""Dynamic calls isolate Frames while retaining native results and status snapshots."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import cast

import pytest

import lclang
import lclang.workflow as wf
from lclang.errors import LclClosedFrameError
from tests.workflow.call_support import Value, make_child, run_parent


@pytest.mark.asyncio
@pytest.mark.parametrize("grouped", [False, True])
async def test_call_results_live_frame_isolation_and_detached_status(
    grouped: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    """The child frame is usable only inside the scope and parent nodes share no status."""
    child = make_child(grouped=grouped)
    results: list[wf.WorkflowExecutionResult] = []

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for index in range(2):
            async with child.execute_in_task(
                context, manager, name=f"call-{index}", preset={"input": index},
            ) as result:
                assert await result.execution_frame.get("output") == index + 1
                assert not result.execution_frame.has("parent_only")
                assert result.task_args[wf.TaskID("child")] == Value(index)
                results.append(result)
            with pytest.raises(LclClosedFrameError):
                await result.execution_frame.get("output")
        assert results[0].execution_frame is not results[1].execution_frame
        assert await context.frame.get("parent_only") == 17
        assert not context.frame.has("output")
        manager.current.sub_tasks[0].sub_tasks[0].task_description = "parent edit"
        return Value(2)

    async with lclang.define_frame(preset={"parent_only": 17}) as frame:
        with caplog.at_level(logging.DEBUG, logger="workflow-call"):
            result = await run_parent(parent, frame)
        assert await frame.get("parent_only") == 17
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert results[0].execution_status is not results[1].execution_status
    native_root = results[0].execution_status.sub_tasks[0]
    native_leaf = native_root.sub_tasks[0] if grouped else native_root
    assert native_leaf.task_description == "Child"
    calls = result.execution_status.sub_tasks[0].sub_tasks
    assert [node.sub_tasks[0].task_name for node in calls] == ["child", "child"]
    assert any("workflow call start: [parent.call-0] Child workflow (dryrun)" in m
               for m in caplog.messages)
    assert any("workflow call complete: [parent.call-0] Child workflow SUCCESS" in m
               for m in caplog.messages)


@pytest.mark.asyncio
async def test_parent_retains_severity_and_publishes_summary_before_stopping_children() -> None:
    """Batch actions can continue after business failures while declared dependants stop."""
    statuses = [wf.ExecutionStatus.FAILURE_COVERED, wf.ExecutionStatus.FAILURE,
                wf.ExecutionStatus.ERROR, wf.ExecutionStatus.SUCCESS]
    observed: list[wf.ExecutionStatus] = []

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for index, status in enumerate(statuses):
            async with make_child(status).execute_in_task(
                context, manager, name=f"item-{index}", preset={"input": index},
            ) as result:
                assert result.execution_status.status is status
            observed.append(manager.current.status)
        return Value(len(observed))

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame, [wf.define_task("after", "Must not run")])
    assert observed == [wf.ExecutionStatus.FAILURE, wf.ExecutionStatus.FAILURE,
                        wf.ExecutionStatus.ERROR, wf.ExecutionStatus.ERROR]
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert result.task_outputs[wf.TaskID("parent")] == Value(4)
    assert result.execution_status.sub_tasks[0].sub_tasks[-1].status is wf.ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_metadata_shared_explicit_objects_and_context_root_retention() -> None:
    """Only explicit objects cross the Frame boundary; task contexts close before yielding."""
    shared: list[str] = []

    @asynccontextmanager
    async def resource(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncIterator[Value]:
        values = cast(list[str], await context.frame.get("shared"))
        assert values is shared
        assert context.is_dryrun and context.verbose_mode
        assert context.as_of_date.day == 23 and context.logger.name == "workflow-call"
        values.append("enter")
        try:
            yield args
        finally:
            values.append("exit")

    root = wf.define_task("resource_root", "Resource root", context_tasks=[
        wf.define_context_task("resource", "Resource", resource, Value(1)),
    ])
    workflow = wf.define_workflow("Resource workflow", root, lcl_mixin={"own": 9})

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for index in range(2):
            async with workflow.execute_in_task(
                context, manager, name=f"resource-{index}", preset={"shared": shared, "own": 1},
            ) as result:
                assert await result.execution_frame.get("own") == 9
                assert len(shared) == 2 * (index + 1)
                assert manager.current.sub_tasks[-1].sub_tasks[0].task_name == "resource_root"
        return Value(2)

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame)
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert shared == ["enter", "exit", "enter", "exit"]


@pytest.mark.asyncio
async def test_call_preflight_rejects_invalid_names_and_parents_before_execution() -> None:
    """Invalid destinations never execute a child with side effects."""
    child = make_child()

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for name in ("", "reserved"):
            with pytest.raises(ValueError):
                async with child.execute_in_task(context, manager, name=name):
                    pytest.fail("entered")
        for bad_context, bad_manager in ((None, manager), (context, None)):
            with pytest.raises(TypeError):
                async with child.execute_in_task(
                    cast(wf.TaskContext, bad_context), cast(wf.ExecutionStatusManager, bad_manager),
                    name="invalid",
                ):
                    pytest.fail("entered")
        inactive = replace(context)
        with pytest.raises(RuntimeError, match="active|action"):
            async with child.execute_in_task(inactive, manager, name="inactive"):
                pytest.fail("entered")
        for invalid_parent in (
            wf.ExecutionStatusManager("step", task_type=wf.ExecutionTaskType.STEP),
            wf.ExecutionStatusManager("locked"),
        ):
            if invalid_parent.current.task_name == "locked":
                invalid_parent.finalize()
            with pytest.raises((ValueError, RuntimeError)):
                async with child.execute_in_task(context, invalid_parent, name="invalid"):
                    pytest.fail("entered")
        async with child.execute_in_task(context, manager, name="used", preset={"input": 1}):
            pass
        with pytest.raises(ValueError, match="conflicts"):
            async with child.execute_in_task(context, manager, name="used"):
                pytest.fail("entered")
        return Value(1)

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame, [wf.define_task("reserved", "Reserved")])
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
