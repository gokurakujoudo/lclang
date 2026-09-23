"""Scoped workflow calls retain results while distinguishing operational failures."""

from collections.abc import Mapping
from typing import cast

import pytest

import lclang
import lclang.workflow as wf
from lclang.runtime import Frame
from tests.workflow.call_support import Value, install_call_resource, make_child, run_parent


@pytest.mark.asyncio
async def test_setup_failure_propagates_without_borrowing_parent_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creation errors have no fake child result and never close the parent Frame."""
    failure = OSError("cannot create frame")

    def fail() -> Frame:
        raise failure

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        monkeypatch.setattr("lclang.workflow.calls.define_frame", fail)
        with pytest.raises(OSError) as caught:
            async with make_child().execute_in_task(context, manager, name="creation"):
                pytest.fail("entered")
        assert caught.value is failure
        assert manager.current.sub_tasks[0].status is wf.ExecutionStatus.ERROR
        assert await context.frame.get("alive") == 1
        return Value(1)

    async with lclang.define_frame(preset={"alive": 1}) as frame:
        result = await run_parent(parent, frame)
        assert await frame.get("alive") == 1
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert result.task_outputs[wf.TaskID("parent")] == Value(1)


@pytest.mark.asyncio
async def test_preflight_binding_errors_create_no_call_nodes() -> None:
    """Bad bindings fail before executing or mounting anything."""
    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for preset in (1, {1: 2}):
            with pytest.raises(TypeError):
                async with make_child().execute_in_task(
                    context, manager, name="bad", preset=cast(Mapping[str, object], preset),
                ):
                    pytest.fail("entered")
        assert not manager.current.sub_tasks
        return Value(1)

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame)
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_unexpected_execution_exception_yields_error_with_live_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failures before the native executor can make a result still allow inspection."""
    child = wf.define_workflow("Empty", wf.define_task("group", "Empty group"))
    execute = wf.Workflow.execute

    async def fail(
        self: wf.Workflow, context: wf.WorkflowExecutionContext,
    ) -> wf.WorkflowExecutionResult:
        if self is child:
            raise ValueError("unexpected execution error")
        return await execute(self, context)

    monkeypatch.setattr(wf.Workflow, "execute", fail)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with child.execute_in_task(context, manager, name="execute") as result:
            assert result.execution_status.status is wf.ExecutionStatus.ERROR
            assert not result.task_args and not result.task_outputs
            assert not result.execution_frame.has("anything")
            assert "unexpected execution" in result.execution_status.task_description
        return Value(1)

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame)
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert result.task_outputs[wf.TaskID("parent")] == Value(1)


@pytest.mark.asyncio
@pytest.mark.parametrize("body_error,cleanup_error", [(True, False), (False, True), (True, True)])
async def test_body_and_cleanup_errors_preserve_native_values(
    body_error: bool, cleanup_error: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cleanup errors escape the scope without throwing away materialized child outputs."""
    body_failure = ValueError("body failed")
    cleanup_failure = OSError("close failed")

    class Resource:
        def close(self) -> None:
            if cleanup_error:
                raise cleanup_failure

    install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        with pytest.raises(Exception) as caught:
            async with make_child().execute_in_task(
                context, manager, name="errors", preset={"input": 4},
            ) as result:
                assert isinstance(await result.execution_frame.get("resource"), Resource)
                if body_error:
                    raise body_failure
        if body_error and cleanup_error:
            assert isinstance(caught.value, ExceptionGroup)
            assert caught.value.exceptions[0] is body_failure
            assert caught.value.exceptions[1].__cause__ is cleanup_failure
        elif cleanup_error:
            assert caught.value.__cause__ is cleanup_failure
        else:
            assert caught.value is body_failure
        assert result.task_args[wf.TaskID("child")] == Value(4)
        assert result.task_outputs[wf.TaskID("child")] == Value(5)
        assert result.execution_status.status is (
            wf.ExecutionStatus.ERROR if cleanup_error else wf.ExecutionStatus.SUCCESS
        )
        assert result.execution_status.sub_tasks[0].status is wf.ExecutionStatus.SUCCESS
        assert manager.current.sub_tasks[0].status is wf.ExecutionStatus.ERROR
        return Value(1)

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame)
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert result.task_outputs[wf.TaskID("parent")] == Value(1)
