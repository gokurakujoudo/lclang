"""Workflow logs preserve operational paths, callback durations and stopping semantics."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import date
from typing import cast

import pytest

from lclang.error import LclValidationError, WorkflowStatusStop
from lclang.lang import Frame, define_frame
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    TaskContext,
    TaskID,
    WorkflowExecutionContext,
    define_context_task,
    define_task,
    define_variable,
    define_workflow,
)
from lclang.workflow.mappings import mapped_outputs, materialize_args
from lclang.workflow.task_logging import log_task_error


@dataclass
class Value:
    """Minimal typed workflow arguments and outputs."""

    count: int


def execution(frame: Frame, logger: logging.Logger) -> WorkflowExecutionContext:
    """Build a deterministic verbose execution context."""
    return WorkflowExecutionContext(False, date(2026, 10, 13), True, logger, frame)


@pytest.mark.asyncio
async def test_nested_calls_keep_full_log_paths_and_local_business_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent call names extend log paths without changing local business IDs."""
    observed: list[tuple[list[TaskID], str, tuple[str, ...]]] = []

    async def leaf(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        observed.append(
            (
                context.task_id_stack,
                str(await context.frame.get("__task_id_branch__")),
                context.log_task_stack,
            )
        )
        context.log_event("saved", count=args.count)
        await asyncio.sleep(0)
        return args

    child = define_workflow(
        "File", define_task("leaf", "Leaf", task_action=leaf, args_mapping=Value(1))
    )

    async def parent(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        async def call(name: str) -> None:
            async with child.execute_in_task(context, status_mgr, name=name) as result:
                assert result.task_outputs[TaskID("leaf")] == Value(1)
                context.log_event("parent body")

        await asyncio.gather(call("a.csv"), call("b.csv"))
        return args

    root = define_workflow(
        "Batch", define_task("batch", "Batch", task_action=parent, args_mapping=Value(1))
    )
    logger = logging.getLogger("full-log-paths")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        async with define_frame() as frame:
            result = await root.execute(execution(frame, logger))
    assert result.execution_status.status is ExecutionStatus.SUCCESS
    assert {stack for _, _, stack in observed} == {
        ("batch", "a.csv", "leaf"),
        ("batch", "b.csv", "leaf"),
    }
    assert all(local == [TaskID("leaf")] and branch == "leaf" for local, branch, _ in observed)
    events = [r for r in caplog.records if getattr(r, "lclang_event", None) == "saved"]
    assert {r.__dict__["lclang_task_branch"] for r in events} == {
        "batch.a.csv.leaf",
        "batch.b.csv.leaf",
    }
    assert all(
        r.getMessage().startswith(f"[{r.__dict__['lclang_task_branch']}] | saved\n") for r in events
    )
    assert all(
        r.__dict__["lclang_task_branch"] == "batch"
        for r in caplog.records
        if getattr(r, "lclang_event", None) == "parent body"
    )
    assert any("args mapping: [batch.a.csv.leaf]" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_callback_durations_exclude_child_traversal_and_context_holding(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An independent controlled clock distinguishes callback work from resource holding."""
    clock = [0]
    monkeypatch.setattr("time.perf_counter_ns", lambda: clock[0])

    @asynccontextmanager
    async def scope(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        clock[0] += 2_000_000
        yield args
        clock[0] += 3_000_000

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        clock[0] += args.count * 1_000_000
        return args

    child = define_task("child", "Child", task_action=action, args_mapping=Value(100))
    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(5),
        children=(child,),
        context_tasks=(define_context_task("scope", "Scope", scope, Value(1)),),
    )
    logger = logging.getLogger("callback-times")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            await define_workflow("Times", task).execute(execution(frame, logger))
    assert "Workflow task completed: [root] SUCCESS action_ms=5.000" in caplog.messages
    assert "Workflow task completed: [root.child] SUCCESS action_ms=100.000" in caplog.messages
    assert (
        "Workflow task completed: [root.scope] SUCCESS enter_ms=2.000 exit_ms=3.000"
        in caplog.messages
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [ExecutionStatus.ERROR, ExecutionStatus.FAILURE, ExecutionStatus.FAILURE_COVERED]
)
async def test_status_stop_and_context_unwind_are_warning_records(
    caplog: pytest.LogCaptureFixture,
    status: ExecutionStatus,
) -> None:
    """Stopping status remains failed while normal context unwinding reports no new exception."""
    received: list[WorkflowStatusStop] = []

    @asynccontextmanager
    async def scope(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        except WorkflowStatusStop as stopped:
            received.append(stopped)
            context.log_event(
                f"{stopped.message}; skipped: success notification", level=logging.WARNING
            )
            raise

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        status_mgr.update(status)
        return args

    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=(define_context_task("scope", "Scope", scope, Value(1)),),
    )
    logger = logging.getLogger("stopping-warnings")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            result = await define_workflow("Stop", task).execute(execution(frame, logger))
    assert result.execution_status.status is status and len(received) == 1
    stopped = next(r for r in caplog.records if "Workflow task stopped:" in r.getMessage())
    assert stopped.levelno == logging.WARNING and stopped.exc_info is None
    assert (
        f"task 'root' ended with {status.value}" in stopped.getMessage()
        and "skipped:" in stopped.getMessage()
    )
    event = next(r for r in caplog.records if getattr(r, "lclang_event", None))
    assert (
        event.getMessage()
        == f"[root.scope] | task 'root' ended with {status.value}; skipped: success notification"
    )
    assert event.levelno == logging.WARNING and event.exc_info is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,code",
    [(None, "LCL533131"), (["root"], "LCL533131"), ((3,), "LCL533131"), (("",), "LCL533211")],
)
async def test_log_path_fields_validate_without_changing_business_stacks(
    value: object, code: str
) -> None:
    """Both additive path fields reject untyped invalid inputs with specific codes."""
    logger = logging.Logger("path-validation")
    task = define_task("root", "Root")
    async with define_frame() as frame:
        public = execution(frame, logger)
        context = TaskContext(
            False, date(2026, 10, 13), False, logger, frame, task, [TaskID("root")]
        )
        factories = (
            lambda: replace(public, log_task_prefix=cast(tuple[str, ...], value)),
            lambda: replace(context, log_task_stack=cast(tuple[str, ...], value)),
        )
        for factory in factories:
            with pytest.raises(LclValidationError) as caught:
                factory()
            assert caught.value.code == code
        assert context.task_id_stack == [TaskID("root")] and context.log_task_stack == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["mapping", "action", "enter", "exit"])
async def test_failed_callbacks_keep_only_started_phase_durations(
    stage: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unstarted callbacks omit durations while failed bodies retain measured time."""
    clock = [0]
    monkeypatch.setattr("time.perf_counter_ns", lambda: clock[0])

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        clock[0] += 7_000_000
        raise OSError("body failed")

    @asynccontextmanager
    async def scope(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        clock[0] += 2_000_000
        if stage == "enter":
            raise OSError("enter failed")
        try:
            yield args
        finally:
            clock[0] += 3_000_000
            if stage == "exit":
                raise OSError("exit failed")

    contexts = (
        ()
        if stage in {"mapping", "action"}
        else (define_context_task("scope", "Scope", scope, Value(1)),)
    )
    mapping = Value(define_variable[int]("missing").quote) if stage == "mapping" else Value(1)
    task = define_task(
        "root", "Root", task_action=action, args_mapping=mapping, context_tasks=contexts
    )
    logger = logging.getLogger("failed-times")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            result = await define_workflow("Failed times", task).execute(execution(frame, logger))
    assert result.execution_status.status is ExecutionStatus.ERROR
    completed = [
        message for message in caplog.messages if message.startswith("Workflow task completed:")
    ]
    root = next(message for message in completed if "[root]" in message)
    assert root == "Workflow task completed: [root] ERROR" + (
        " action_ms=7.000" if stage in {"action", "exit"} else ""
    )
    if contexts:
        assert completed[0] == "Workflow task completed: [root.scope] ERROR enter_ms=2.000" + (
            " exit_ms=3.000" if stage == "exit" else ""
        )


@pytest.mark.asyncio
async def test_stop_with_cleanup_failure_retains_real_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed exit preserves the earlier stop in the complete cleanup error group."""

    @asynccontextmanager
    async def scope(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        finally:
            raise OSError("cleanup failed")

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        status_mgr.update(ExecutionStatus.ERROR)
        return args

    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=(define_context_task("scope", "Scope", scope, Value(1)),),
    )
    logger = logging.getLogger("stop-cleanup")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            result = await define_workflow("Cleanup", task).execute(execution(frame, logger))
    assert result.execution_status.status is ExecutionStatus.ERROR
    record = next(
        record
        for record in caplog.records
        if record.getMessage().startswith("Workflow task error: [root.scope]")
    )
    assert record.levelno == logging.ERROR and record.exc_info is not None
    assert "LCL531991" in record.getMessage() and "LCL532812" in record.getMessage()
    assert "cleanup failed" in record.getMessage()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relation,suppressed", [("cause", False), ("context", False), ("context", True)]
)
async def test_stop_with_attached_failure_is_not_silenced(
    relation: str, suppressed: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """Isolated stopping signals warn; attached failure evidence remains an error diagnostic."""
    error = WorkflowStatusStop("task stopped")
    if relation == "cause":
        error.__cause__ = OSError("attached failure")
    else:
        error.__context__ = OSError("attached failure")
        error.__suppress_context__ = suppressed
    logger = logging.getLogger("attached-stop")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        async with define_frame() as frame:
            log_task_error(
                execution(frame, logger), (TaskID("root"),), ExecutionStatus.ERROR, error
            )
    record = caplog.records[-1]
    if suppressed:
        assert record.levelno == logging.WARNING and record.exc_info is None
        assert "attached failure" not in record.getMessage()
    else:
        assert record.levelno == logging.ERROR and record.exc_info is not None
        assert "attached failure" in record.getMessage()


@pytest.mark.asyncio
async def test_cancelled_action_keeps_body_timing_and_unwinds_resources(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Native cancellation survives measured action and context scopes unchanged."""
    clock = [0]
    monkeypatch.setattr("time.perf_counter_ns", lambda: clock[0])
    cancelled = asyncio.CancelledError("cancelled body")
    cleaned: list[bool] = []

    @asynccontextmanager
    async def scope(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        finally:
            clock[0] += 3_000_000
            cleaned.append(True)

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        clock[0] += 7_000_000
        raise cancelled

    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(1),
        context_tasks=(define_context_task("scope", "Scope", scope, Value(1)),),
    )
    logger = logging.getLogger("cancelled-times")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            with pytest.raises(asyncio.CancelledError) as caught:
                await define_workflow("Cancel", task).execute(execution(frame, logger))
    assert caught.value is cancelled and cleaned == [True]
    root = next(
        message
        for message in caplog.messages
        if message.startswith("Workflow task completed: [root]")
    )
    assert root.endswith("action_ms=7.000")
    context = next(
        message
        for message in caplog.messages
        if message.startswith("Workflow task completed: [root.scope]")
    )
    assert context.endswith("enter_ms=0.000 exit_ms=3.000")


@pytest.mark.asyncio
async def test_concurrent_executions_and_nested_calls_do_not_share_log_prefixes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Three-level calls compose each execution's prefix and retain parent callback identity."""

    async def leaf(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        context.log_event("leaf")
        return args

    inner = define_workflow(
        "Inner", define_task("leaf", "Leaf", task_action=leaf, args_mapping=Value(1))
    )

    async def middle(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        async with inner.execute_in_task(context, status_mgr, name="inner.csv"):
            context.log_event("middle body")
        return args

    child = define_workflow(
        "Child", define_task("middle", "Middle", task_action=middle, args_mapping=Value(1))
    )

    async def root(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        async with child.execute_in_task(context, status_mgr, name="outer"):
            context.log_event("root body")
        return args

    workflow = define_workflow(
        "Root", define_task("root", "Root", task_action=root, args_mapping=Value(1))
    )
    logger = logging.getLogger("isolated-log-prefixes")

    async def run(prefix: str) -> None:
        async with define_frame() as frame:
            result = await workflow.execute(
                replace(execution(frame, logger), log_task_prefix=(prefix,))
            )
            assert result.execution_status.status is ExecutionStatus.SUCCESS
            assert set(result.task_outputs) == {TaskID("root")}

    with caplog.at_level(logging.INFO, logger=logger.name):
        await asyncio.gather(run("a"), run("b"))
    leaves = {
        record.getMessage()
        for record in caplog.records
        if getattr(record, "lclang_event", None) == "leaf"
    }
    assert leaves == {
        "[a.root.outer.middle.inner.csv.leaf] | leaf",
        "[b.root.outer.middle.inner.csv.leaf] | leaf",
    }
    parents = {
        record.getMessage()
        for record in caplog.records
        if getattr(record, "lclang_event", None) == "root body"
    }
    assert parents == {"[a.root] | root body", "[b.root] | root body"}


@pytest.mark.asyncio
async def test_action_timing_includes_dynamic_calls_but_excludes_own_mapping_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A child call's work belongs to the caller body; each task excludes its own overhead."""
    clock = [0]
    monkeypatch.setattr("time.perf_counter_ns", lambda: clock[0])
    original_close = Frame.close

    async def map_args(mapping: object, frame: Frame) -> object:
        clock[0] += 100_000_000
        return await materialize_args(mapping, frame)

    async def publish(mapping: object | None, output: object, frame: Frame) -> dict[str, object]:
        clock[0] += 200_000_000
        return await mapped_outputs(mapping, output, frame)

    async def close(frame: Frame) -> None:
        await original_close(frame)
        clock[0] += 50_000_000

    monkeypatch.setattr("lclang.workflow.task_execution.materialize_args", map_args)
    monkeypatch.setattr("lclang.workflow.task_execution.mapped_outputs", publish)
    monkeypatch.setattr(Frame, "close", close)

    async def leaf(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        clock[0] += 7_000_000
        return args

    child = define_workflow(
        "Child", define_task("leaf", "Leaf", task_action=leaf, args_mapping=Value(1))
    )

    async def action(
        context: TaskContext, args: Value, status_mgr: ExecutionStatusManager
    ) -> Value:
        clock[0] += 5_000_000
        async with child.execute_in_task(context, status_mgr, name="child"):
            clock[0] += 3_000_000
        return args

    workflow = define_workflow(
        "Root", define_task("root", "Root", task_action=action, args_mapping=Value(1))
    )
    logger = logging.getLogger("dynamic-call-times")
    with caplog.at_level(logging.INFO, logger=logger.name):
        async with define_frame() as frame:
            result = await workflow.execute(execution(frame, logger))
    assert result.execution_status.status is ExecutionStatus.SUCCESS
    assert "Workflow task completed: [root.child.leaf] SUCCESS action_ms=7.000" in caplog.messages
    assert "Workflow task completed: [root] SUCCESS action_ms=415.000" in caplog.messages
