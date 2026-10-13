"""Verbose mapping failures preserve workflow effects and original failures."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import cast

import pytest

from lclang.error import LclError, WorkflowException
from lclang.lang import define_frame
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
    task_logging,
)
from tests.support.verbose_failures import FailingVerboseLogger


@dataclass
class Value:
    """One business value whose publication must survive diagnostic failure."""

    value: int


@dataclass
class FragileRecord:
    """A valid business record with a field unavailable to diagnostic readers."""

    value: int
    fragile: object = None

    def __getattribute__(self, name: str) -> object:
        """Fail diagnostic access to one field while allowing business reads."""
        if name == "fragile":
            raise ValueError("diagnostic field unavailable")
        return object.__getattribute__(self, name)


@pytest.mark.asyncio
@pytest.mark.parametrize("verbose", [False, True])
@pytest.mark.parametrize("masked", [False, True])
async def test_unreadable_record_fields_cannot_prevent_business_execution(
    caplog: pytest.LogCaptureFixture,
    verbose: bool,
    masked: bool,
) -> None:
    """Real field-getter failures leave whole-record inputs and publication intact."""
    source = define_variable[FragileRecord]("source", is_masked=masked)
    target = define_variable[FragileRecord]("target", is_masked=masked)
    original = FragileRecord(42)
    events: list[int] = []

    async def action(
        context: TaskContext,
        args: FragileRecord,
        status_mgr: ExecutionStatusManager,
    ) -> FragileRecord:
        events.append(args.value)
        return args

    task = define_task(
        "root", "Root", task_action=action, args_mapping=source.quote, outputs_mapping=target.quote
    )
    logger = logging.getLogger("fragile-record")
    async with define_frame(preset={"source": original}) as frame:
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            result = await define_workflow("Fragile", task).execute(
                WorkflowExecutionContext(False, date(2026, 10, 13), verbose, logger, frame)
            )
        assert result.execution_status.status is ExecutionStatus.SUCCESS
        assert result.task_args[TaskID("root")] is original
        assert await frame.get("target") is original
        assert events == [42]
    assert "diagnostic field unavailable" not in caplog.text
    if verbose and masked:
        assert "*masked*" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["argument", "output", "write", "handler"])
@pytest.mark.parametrize("failure_mode", ["success", "action", "cleanup", "both"])
async def test_verbose_failures_preserve_context_effects_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    failure_mode: str,
) -> None:
    """Context and action mappings cannot prevent effects or replace composite errors."""
    business_error = ValueError("business failed")
    cleanup_error = RuntimeError("cleanup failed")
    events: list[str] = []
    published = define_variable[int]("published")
    original_message = task_logging.mapping_message

    def render(
        context: WorkflowExecutionContext,
        branch: tuple[TaskID, ...],
        mapping: object | None,
        value: object,
        *,
        output: bool,
    ) -> str:
        """Fail only the selected diagnostic phase."""
        if (boundary == "output" and output) or (boundary == "argument" and not output):
            raise RuntimeError("mapping renderer failed")
        return original_message(context, branch, mapping, value, output=output)

    monkeypatch.setattr(task_logging, "mapping_message", render)

    @asynccontextmanager
    async def scope(
        context: TaskContext,
        args: Value,
        status_mgr: ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        try:
            yield args
        finally:
            events.append("exit")
            if failure_mode in ("cleanup", "both"):
                raise cleanup_error

    async def action(
        context: TaskContext,
        args: Value,
        status_mgr: ExecutionStatusManager,
    ) -> Value:
        events.append("action")
        if failure_mode in ("action", "both"):
            raise business_error
        return Value(args.value + 2)

    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(40),
        outputs_mapping=Value(published.quote),
        context_tasks=[define_context_task("scope", "Scope", scope, Value(40))],
    )
    logger = FailingVerboseLogger(boundary)
    async with define_frame() as frame:
        result = await define_workflow("Isolation", task).execute(
            WorkflowExecutionContext(False, date(2026, 10, 13), True, logger, frame)
        )
        assert events == ["enter", "action", "exit"]
        if failure_mode == "success":
            assert result.execution_status.status is ExecutionStatus.SUCCESS
            assert await frame.get("published") == 42
            assert cast(Value, result.task_outputs[TaskID("root")]).value == 42
        else:
            assert result.execution_status.status is ExecutionStatus.ERROR
            failure = cast(WorkflowException, await frame.get("__exception__"))
            members = (
                cast(BaseExceptionGroup[BaseException], failure.exception).exceptions
                if isinstance(failure.exception, BaseExceptionGroup)
                else (failure.exception,)
            )
            causes = [
                member.__cause__ if isinstance(member, LclError) else member for member in members
            ]
            expected: list[Exception] = []
            if failure_mode in ("action", "both"):
                expected.append(business_error)
            if failure_mode in ("cleanup", "both"):
                expected.append(cleanup_error)
            assert causes == expected
            if failure_mode == "cleanup":
                assert await frame.get("published") == 42
            else:
                assert not frame.has("published")


@pytest.mark.asyncio
async def test_broken_verbose_sink_cannot_replace_cancellation_during_context_cleanup() -> None:
    """A failed final DEBUG write preserves cancellation after owned scope unwinding."""
    cancellation = asyncio.CancelledError("business cancellation")
    events: list[str] = []

    @asynccontextmanager
    async def scope(
        context: TaskContext,
        args: Value,
        status_mgr: ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        events.append("enter")
        try:
            yield args
        finally:
            events.append("exit")

    async def action(
        context: TaskContext,
        args: Value,
        status_mgr: ExecutionStatusManager,
    ) -> Value:
        events.append("cancel")
        raise cancellation

    task = define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=Value(40),
        context_tasks=[define_context_task("scope", "Scope", scope, Value(40))],
    )
    async with define_frame() as frame:
        with pytest.raises(asyncio.CancelledError) as caught:
            await define_workflow("Cancellation", task).execute(
                WorkflowExecutionContext(
                    False, date(2026, 10, 13), True, FailingVerboseLogger("write"), frame
                )
            )
        assert caught.value is cancellation
        assert events == ["enter", "cancel", "exit"]
        assert not frame.has("__exception__")
