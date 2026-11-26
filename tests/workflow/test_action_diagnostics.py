"""Unexpected action-stage failures retain status and native diagnostics."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date

import pytest

import lclang.workflow as wf
from lclang.error import LclError, LclErrorGroup, LclWorkflowError, WorkflowException
from lclang.error.failure_aggregation import contains_failure
from lclang.lang import define_frame
from tests.workflow.call_support import Value, install_call_resource, make_child, run_parent


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_error", [False, True])
async def test_return_annotation_failure_records_action_error_and_cause(
    explicit_error: bool,
) -> None:
    """A post-callback annotation failure cannot become a successful workflow."""

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        if explicit_error:
            status_mgr.update(wf.ExecutionStatus.ERROR, "earlier action status")
        action.__annotations__["return"] = "MissingWorkflowResult"
        return args

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        children=[wf.define_task("later", "Later")],
    )
    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 1, 1), False, logging.getLogger("action-diagnostics"), frame
        )
        result = await wf.define_workflow("Workflow", task).execute(context)
        diagnostic = await frame.get("__exception__", fallback=None)

    root = result.execution_status.sub_tasks[0]
    action_node, later = root.sub_tasks
    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert root.status is wf.ExecutionStatus.ERROR
    assert action_node.task_name == "root$action"
    assert action_node.status is wf.ExecutionStatus.ERROR
    assert later.task_name == "later"
    assert later.status is wf.ExecutionStatus.SKIPPED
    assert isinstance(diagnostic, WorkflowException)
    assert isinstance(diagnostic.exception, LclError)
    assert isinstance(diagnostic.exception.__cause__, NameError)
    assert "MissingWorkflowResult" in str(diagnostic.exception.__cause__)


@pytest.mark.asyncio
async def test_existing_lcl_group_keeps_implicit_context_in_action_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recording an existing group preserves its original implicit exception context."""
    prior = ValueError("original operation")
    group = LclErrorGroup(
        "combined failure", [OSError("first"), OSError("second")], code="APP/ACTION"
    )

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        try:
            raise prior
        except ValueError:
            # Exercise Python's implicit exception context rather than an explicit cause.
            raise group  # noqa: B904

    task = wf.define_task("root", "Root", task_action=action, args_mapping=Value(1))
    logger = logging.getLogger("existing-group-context")
    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(False, date(2026, 1, 1), False, logger, frame)
        with caplog.at_level(logging.ERROR, logger=logger.name):
            result = await wf.define_workflow("Workflow", task).execute(context)
        diagnostic = await frame.get("__exception__")

    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    assert isinstance(diagnostic, WorkflowException)
    assert diagnostic.exception is group
    assert group.__context__ is prior
    assert group.__cause__ is None
    assert not group.__suppress_context__
    failures = [
        record.getMessage() for record in caplog.records if "Workflow task error:" in record.message
    ]
    assert len(failures) == 1
    assert "APP/ACTION" in failures[0]
    assert "During handling" in failures[0]
    assert "ValueError: original operation" in failures[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("cover", [False, True])
async def test_nested_failure_cleans_up_and_records_unreached_subtrees(cover: bool) -> None:
    """Recovery continues outside the failed subtree after its context is released."""
    events: list[str] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        try:
            yield args
        except LclWorkflowError as error:
            assert isinstance(error.__cause__, ValueError)
            if not cover:
                raise
            events.append("covered")
            status_mgr.update(wf.ExecutionStatus.FAILURE_COVERED)
        finally:
            events.append("cleanup")

    async def fail(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append("failed")
        raise ValueError("business failure")

    async def later(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        events.append(str(context.task_id_stack[-1]))
        return args

    grandchild = wf.define_task(
        "grandchild", "Grandchild", task_action=later, args_mapping=Value(1)
    )
    unreached = wf.define_task(
        "unreached", "Unreached", task_action=later, args_mapping=Value(1), children=[grandchild]
    )
    failed = wf.define_task(
        "failed",
        "Failed",
        task_action=fail,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("scope", "Scope", scope, Value(1))],
        children=[unreached],
    )
    after = wf.define_task("after", "After", task_action=later, args_mapping=Value(2))
    branch = wf.define_task("branch", "Branch", children=[failed, after])
    outer = wf.define_task("outer", "Outer", task_action=later, args_mapping=Value(3))
    root = wf.define_task("root", "Root", children=[branch, outer])

    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 1, 1), False, logging.getLogger("nested-diagnostics"), frame
        )
        result = await wf.define_workflow("Workflow", root).execute(context)

    root_status = result.execution_status.sub_tasks[0]
    branch_status, outer_status = root_status.sub_tasks
    failed_status, after_status = branch_status.sub_tasks
    scope_status, action_status, unreached_status = failed_status.sub_tasks
    unreached_action, grandchild_status = unreached_status.sub_tasks
    assert events == (
        ["enter", "failed", "covered", "cleanup", "after", "outer"]
        if cover
        else ["enter", "failed", "cleanup"]
    )
    expected = wf.ExecutionStatus.FAILURE_COVERED if cover else wf.ExecutionStatus.ERROR
    assert result.execution_status.status is expected
    assert root_status.status is expected
    assert branch_status.status is expected
    assert failed_status.status is expected
    assert scope_status.status is (
        wf.ExecutionStatus.FAILURE_COVERED if cover else wf.ExecutionStatus.SUCCESS
    )
    assert action_status.task_name == "failed$action"
    assert action_status.status is wf.ExecutionStatus.ERROR
    assert unreached_status.status is wf.ExecutionStatus.SKIPPED
    assert unreached_action.task_name == "unreached$action"
    assert unreached_action.status is wf.ExecutionStatus.SKIPPED
    assert grandchild_status.status is wf.ExecutionStatus.SKIPPED
    assert grandchild_status.sub_tasks[0].task_name == "grandchild$action"
    assert grandchild_status.sub_tasks[0].status is wf.ExecutionStatus.SKIPPED
    later_status = wf.ExecutionStatus.SUCCESS if cover else wf.ExecutionStatus.SKIPPED
    assert after_status.status is later_status
    assert outer_status.status is later_status
    assert ("after" in result.task_outputs) is cover
    assert ("outer" in result.task_outputs) is cover


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_dynamic_call_cancellation_logs_only_real_cleanup_errors(
    fail_cleanup: bool, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A pure cancellation is reported as interrupted; cleanup failures remain errors."""
    cancelled = asyncio.CancelledError("stop child")
    cleanup_error = OSError("resource close failed")

    class Resource:
        def close(self) -> None:
            if fail_cleanup:
                raise cleanup_error

    install_call_resource(monkeypatch, Resource)

    async def child_action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        await context.frame.get("resource")
        raise cancelled

    child = wf.define_workflow(
        "Child",
        wf.define_task("child", "Child", task_action=child_action, args_mapping=Value(1)),
    )

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with child.execute_in_task(context, manager, name="call"):
            pytest.fail("cancelled child yielded a result")

    async with define_frame() as frame:
        with caplog.at_level(logging.WARNING, logger="workflow-call"):
            with pytest.raises(asyncio.CancelledError) as caught:
                await run_parent(parent, frame)

    assert caught.value is cancelled
    call_errors = [record for record in caplog.records if "Workflow call error:" in record.message]
    completions = [
        record for record in caplog.records if "Workflow call completed:" in record.message
    ]
    assert len(completions) == 1
    if fail_cleanup:
        assert caught.value.__cause__ is not None
        assert contains_failure(caught.value.__cause__, cleanup_error)
        assert len(call_errors) == 1 and call_errors[0].levelno == logging.ERROR
        assert completions[0].levelno == logging.ERROR
        assert " ERROR" in completions[0].message
    else:
        assert not call_errors
        assert completions[0].levelno == logging.WARNING
        assert " FAILURE" in completions[0].message


@pytest.mark.asyncio
async def test_context_cleanup_control_group_retains_ordinary_failure() -> None:
    """A mixed cleanup group leaves the completed action intact and fails the context."""
    cleanup_error = OSError("context cleanup failed")
    group = BaseExceptionGroup(
        "context cleanup",
        [asyncio.CancelledError("stop cleanup"), ExceptionGroup("nested", [cleanup_error])],
    )
    contexts: list[wf.ExecutionStatusTree] = []
    actions: list[wf.ExecutionStatusTree] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        contexts.append(status_mgr.current)
        yield args
        raise group

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        actions.append(status_mgr.current)
        return args

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("scope", "Scope", scope, Value(1))],
    )
    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 1, 1), False, logging.getLogger("mixed-context-cleanup"), frame
        )
        with pytest.raises(BaseExceptionGroup) as caught:
            await wf.define_workflow("Workflow", task).execute(context)

    assert caught.value is group
    assert contains_failure(caught.value, cleanup_error)
    assert actions[0].status is wf.ExecutionStatus.SUCCESS
    assert contexts[0].status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_context_enter_control_group_records_error_and_skips_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mixed failure during context entry retains both native group members."""
    cancelled = asyncio.CancelledError("cancel during context entry")
    setup_error = OSError("context entry failed")
    group = BaseExceptionGroup("context entry", [cancelled, setup_error])
    statuses: dict[str, wf.ExecutionStatusTree] = {}
    actions: list[str] = []
    add_sub_task = wf.ExecutionStatusManager.add_sub_task

    def capture_sub_task(
        manager: wf.ExecutionStatusManager,
        name: str,
        description: str,
        status: wf.ExecutionStatus = wf.ExecutionStatus.PENDING,
    ) -> wf.ExecutionStatusManager:
        child = add_sub_task(manager, name, description, status)
        statuses[name] = child.current
        return child

    monkeypatch.setattr(wf.ExecutionStatusManager, "add_sub_task", capture_sub_task)

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        if args.value == 1:
            raise group
        yield args

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        actions.append("action")
        return args

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("scope", "Scope", scope, Value(1))],
    )
    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 1, 1), False, logging.getLogger("mixed-context-entry"), frame
        )
        with pytest.raises(BaseExceptionGroup) as caught:
            await wf.define_workflow("Workflow", task).execute(context)

    assert caught.value is group
    assert contains_failure(caught.value, cancelled)
    assert contains_failure(caught.value, setup_error)
    assert statuses["scope"].status is wf.ExecutionStatus.ERROR
    assert statuses["root"].status is wf.ExecutionStatus.ERROR
    assert statuses["root$action"].status is wf.ExecutionStatus.SKIPPED
    assert not actions


@pytest.mark.asyncio
async def test_dynamic_call_cleanup_control_group_retains_ordinary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mixed Frame cleanup group preserves the completed child and fails the call."""
    cleanup_error = OSError("Frame cleanup failed")
    group = BaseExceptionGroup(
        "Frame cleanup",
        [asyncio.CancelledError("stop cleanup"), ExceptionGroup("nested", [cleanup_error])],
    )
    results: list[wf.WorkflowExecutionResult] = []
    calls: list[wf.ExecutionStatusTree] = []

    class Resource:
        def close(self) -> None:
            raise group

    install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child().execute_in_task(
            context, manager, name="call", preset={"input": 1}
        ) as result:
            results.append(result)
            calls.append(manager.current.sub_tasks[-1])
            await result.execution_frame.get("resource")
        return Value(1)

    async with define_frame() as frame:
        with pytest.raises(BaseExceptionGroup) as caught:
            await run_parent(parent, frame)

    assert caught.value is group
    assert contains_failure(caught.value, cleanup_error)
    assert results[0].execution_status.status is wf.ExecutionStatus.SUCCESS
    assert (
        results[0].execution_status.sub_tasks[0].sub_tasks[0].status is wf.ExecutionStatus.SUCCESS
    )
    assert calls[0].status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_context_cleanup_cancellation_cause_retains_ordinary_failure() -> None:
    """A cancelled context exit can carry a separate ordinary cleanup failure."""
    cleanup_error = OSError("context cleanup failed")
    cancelled = asyncio.CancelledError("stop cleanup")
    contexts: list[wf.ExecutionStatusTree] = []
    actions: list[wf.ExecutionStatusTree] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        contexts.append(status_mgr.current)
        yield args
        raise cancelled from cleanup_error

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager
    ) -> Value:
        actions.append(status_mgr.current)
        return args

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=[wf.define_context_task("scope", "Scope", scope, Value(1))],
    )
    async with define_frame() as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 1, 1), False, logging.getLogger("caused-context-cleanup"), frame
        )
        with pytest.raises(asyncio.CancelledError) as caught:
            await wf.define_workflow("Workflow", task).execute(context)

    assert caught.value is cancelled
    assert caught.value.__cause__ is cleanup_error
    assert actions[0].status is wf.ExecutionStatus.SUCCESS
    assert contexts[0].status is wf.ExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_dynamic_call_cleanup_cancellation_cause_retains_ordinary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled Frame close can retain an ordinary failure as its cause."""
    cleanup_error = OSError("Frame cleanup failed")
    cancelled = asyncio.CancelledError("stop cleanup")
    results: list[wf.WorkflowExecutionResult] = []
    calls: list[wf.ExecutionStatusTree] = []

    class Resource:
        def close(self) -> None:
            raise cancelled from cleanup_error

    install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child().execute_in_task(
            context, manager, name="call", preset={"input": 1}
        ) as result:
            results.append(result)
            calls.append(manager.current.sub_tasks[-1])
            await result.execution_frame.get("resource")
        return Value(1)

    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await run_parent(parent, frame)

    assert caught.value is cancelled
    assert caught.value.__cause__ is cleanup_error
    assert results[0].execution_status.status is wf.ExecutionStatus.SUCCESS
    assert calls[0].status is wf.ExecutionStatus.ERROR
