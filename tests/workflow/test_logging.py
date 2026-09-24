"""Behavioural tests for workflow lifecycle and mapping logs."""

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
class LoggedArgs:
    """Arguments covering mapped, default, and literal fields."""

    source: str
    count: int = 2
    mode: str = "normal"


@dataclass
class LoggedOutputs:
    """Outputs covering mapped and unused fields."""

    unused: int
    published: str


def execution_context(
    frame: lclang.Frame,
    logger: logging.Logger,
    *,
    dryrun: bool = False,
    verbose: bool = False,
) -> wf.WorkflowExecutionContext:
    """Build one deterministic logging execution context."""
    return wf.WorkflowExecutionContext(dryrun, date(2026, 8, 29), verbose, logger, frame)


@pytest.mark.asyncio
async def test_task_context_lifecycle_branch_and_verbose_mappings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All task kinds log branches while the action Frame exposes its owner path."""
    secret = wf.define_variable[str]("secret", is_masked=True)
    local = wf.define_variable[str]("local")
    published = wf.define_variable[str]("published")
    observed: list[str] = []

    @asynccontextmanager
    async def scope(
        context: wf.TaskContext,
        args: LoggedArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[LoggedOutputs]:
        del status_mgr
        observed.append(str(await context.frame.get("__task_id_branch__")))
        yield LoggedOutputs(3, args.source)

    async def action(
        context: wf.TaskContext,
        args: LoggedArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> LoggedOutputs:
        del status_mgr
        observed.append(str(await context.frame.get("__task_id_branch__")))
        return LoggedOutputs(7, args.source)

    context_task = wf.define_context_task(
        "scope",
        "Open scope",
        scope,
        LoggedArgs(secret.quote, mode="literal"),
        LoggedOutputs(0, local.quote),
    )
    child = wf.define_task(
        "child",
        "Child",
        task_action=action,
        args_mapping=LoggedArgs("required literal"),
    )
    root = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=LoggedArgs(local.quote, mode="literal"),
        outputs_mapping=LoggedOutputs(0, published.quote),
        context_tasks=(context_task,),
        children=(child,),
    )
    logger = logging.getLogger("workflow-logging")
    async with lclang.define_frame(preset={"secret!": "hidden"}) as frame:
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            result = await wf.define_workflow("Logged", root).execute(
                execution_context(frame, logger, dryrun=True, verbose=True)
            )

    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert observed == ["root", "root", "root.child"]
    messages = [record.getMessage() for record in caplog.records]
    assert "task start: [root] Root (dryrun)" in messages
    assert "task start: [root.scope] Open scope (dryrun)" in messages
    assert "task start: [root.child] Child (dryrun)" in messages
    assert "task complete: [root.scope] SUCCESS" in messages
    assert "task complete: [root.child] SUCCESS" in messages
    assert "task complete: [root] SUCCESS" in messages
    assert any(
        message.startswith("args mapping: [root.scope] LoggedArgs\n")
        and "    count  <- default: (int) 2" in message
        and "    mode   <- literal: (str) 'literal'" in message
        and "    source <- [secret]: (str) *masked*" in message
        for message in messages
    )
    assert any(
        message.startswith("outputs mapping: [root] LoggedOutputs\n")
        and "    published -> [published]: (str) 'hidden'" in message
        and "    unused    -> unused: (int) 7" in message
        for message in messages
    )


@pytest.mark.asyncio
async def test_task_error_keeps_traceback_and_still_completes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An originating error record and finalized completion are both observable."""

    async def fail(
        context: wf.TaskContext,
        args: LoggedArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> LoggedOutputs:
        del context, args, status_mgr
        raise ValueError("broken")

    task = wf.define_task(
        "root",
        "Root",
        task_action=fail,
        args_mapping=LoggedArgs("literal"),
    )
    logger = logging.getLogger("workflow-error-logging")
    async with lclang.define_frame() as frame:
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await wf.define_workflow("Failure", task).execute(
                execution_context(frame, logger)
            )

    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    error = next(
        record for record in caplog.records if record.getMessage().startswith("task error:")
    )
    assert error.getMessage() == "task error: [root] ERROR"
    assert error.exc_info is not None
    assert any(record.getMessage() == "task complete: [root] ERROR" for record in caplog.records)


@pytest.mark.asyncio
async def test_argument_materialization_error_uses_task_lifecycle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A lookup failure before action entry still logs error and completion."""
    missing = wf.define_variable[str]("missing")

    async def unreachable(
        context: wf.TaskContext,
        args: LoggedArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> LoggedOutputs:
        del context, args, status_mgr
        raise AssertionError("action must not run")

    task = wf.define_task(
        "root",
        "Root",
        task_action=unreachable,
        args_mapping=LoggedArgs(missing.quote),
    )
    logger = logging.getLogger("workflow-argument-error-logging")
    async with lclang.define_frame() as frame:
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await wf.define_workflow("Failure", task).execute(
                execution_context(frame, logger)
            )

    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    messages = [record.getMessage() for record in caplog.records]
    assert "task error: [root] ERROR" in messages
    assert "task complete: [root] ERROR" in messages


@pytest.mark.asyncio
async def test_context_output_mapping_error_uses_context_lifecycle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An invalid context resource logs against the appended context branch."""
    published = wf.define_variable[str]("published")

    @asynccontextmanager
    async def invalid_scope(
        context: wf.TaskContext,
        args: LoggedArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[LoggedOutputs]:
        del context, args, status_mgr
        yield cast(LoggedOutputs, object())

    context_task = wf.define_context_task(
        "scope",
        "Scope",
        invalid_scope,
        LoggedArgs("literal"),
        LoggedOutputs(0, published.quote),
    )
    task = wf.define_task("root", "Root", context_tasks=(context_task,))
    logger = logging.getLogger("workflow-context-output-error-logging")
    async with lclang.define_frame() as frame:
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await wf.define_workflow("Failure", task).execute(
                execution_context(frame, logger)
            )

    assert result.execution_status.status is wf.ExecutionStatus.ERROR
    messages = [record.getMessage() for record in caplog.records]
    assert "task error: [root.scope] ERROR" in messages
    assert "task complete: [root.scope] ERROR" in messages
    assert "task complete: [root] ERROR" in messages
