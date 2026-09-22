"""Whole-record variables across task and context mapping boundaries."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import pytest

import lclang
import lclang.workflow as wf


@dataclass
class Record[T]:
    """Generic task record with a constructor default."""

    value: T
    count: int = 1


async def echo(
    context: wf.TaskContext, args: Record[int], status_mgr: wf.ExecutionStatusManager,
) -> Record[int]:
    """Echo the entire materialized argument."""
    return args


@asynccontextmanager
async def resource(
    context: wf.TaskContext, args: Record[int], status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[Record[int]]:
    """Yield one whole-record context resource."""
    yield args


def execution_context(frame: lclang.Frame, verbose: bool = False) -> wf.WorkflowExecutionContext:
    """Build isolated execution metadata without file logging."""
    return wf.WorkflowExecutionContext(
        False, date(2026, 9, 21), verbose, logging.getLogger("record-mappings"), frame,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scoped_input", [False, True])
@pytest.mark.parametrize("scoped_output", [False, True])
async def test_whole_records_read_and_publish(
    scoped_input: bool, scoped_output: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    """Concrete values preserve identity; existing scopes receive direct fields."""
    source = wf.define_variable[Record[int]]("source", "Source")
    target = wf.define_variable[Record[int]]("target", "Target", is_masked=True)
    task = wf.define_task(
        "root", "Root", task_action=echo,
        args_mapping=source.quote, outputs_mapping=target.quote,
    )
    workflow = wf.define_workflow("Records", task)
    assert [item.name for item in workflow.to_cli("run", "Run").parameter_docs] == ["source"]
    assert "Record[int] <- $source" in "\n".join(workflow.to_lines())
    assert "Record[int] -> $target!" in "\n".join(workflow.to_lines())
    original = Record(17)
    values: dict[str, object] = {"source.value": 17} if scoped_input else {"source": original}
    if scoped_output:
        values.update({"target.value": -1, "target.extra": "keep"})
    async with lclang.define_frame(preset=values) as frame:
        with caplog.at_level(logging.DEBUG, logger="record-mappings"):
            result = await workflow.execute(execution_context(frame, True))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        args = result.task_args[wf.TaskID("root")]
        assert args == original
        if not scoped_input:
            assert args is original
        if scoped_output:
            proxy = await frame.get("target")
            assert isinstance(proxy, lclang.FrameProxy)
            assert await proxy.as_record(Record) == original
            assert await frame.get("target.extra") == "keep"
            assert frame.is_masked("target.value")
            assert frame.is_masked("target.count")
        else:
            assert await frame.get("target") is args
            assert frame.is_masked("target")
    outputs = [message for message in caplog.messages if message.startswith("outputs mapping:")]
    assert outputs and "*masked*" in outputs[0] and "17" not in outputs[0]


@pytest.mark.asyncio
async def test_whole_context_records_remain_local() -> None:
    """A context scope can feed the current action without publishing globally."""
    source = wf.define_variable[Record[int]]("source")
    local = wf.define_variable[Record[int]]("local")
    context = wf.define_context_task("resource", "Resource", resource, source.quote, local.quote)
    task = wf.define_task(
        "root", "Root", task_action=echo, args_mapping=local.quote, context_tasks=[context],
    )
    workflow = wf.define_workflow("Records", task)
    assert [item.name for item in workflow.to_cli("run", "Run").parameter_docs] == ["source"]
    async with lclang.define_frame(preset={"source": Record(7), "local.value": -1}) as frame:
        result = await workflow.execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert result.task_args[wf.TaskID("root")] == Record(7)
        assert await frame.get("local.value") == -1
        assert not frame.has("local.count")


@pytest.mark.parametrize("kind", ["args", "outputs", "context_args", "context_outputs"])
@pytest.mark.parametrize("annotation", [int, Record[str]])
def test_whole_mapping_requires_exact_dataclass_annotation(kind: str, annotation: Any) -> None:
    """Scalars and a different generic specialization are rejected at definition."""
    wrong = cast(Any, wf.define_variable)[annotation]("wrong")
    correct = wf.define_variable[Record[int]]("correct")
    args = wrong.quote if kind.endswith("args") else correct.quote
    output = wrong.quote if kind.endswith("outputs") else correct.quote
    with pytest.raises(TypeError, match="dataclass|annotations"):
        if kind.startswith("context"):
            wf.define_context_task("context", "Context", resource, args, output)
        else:
            wf.define_task(
                "root", "Root", task_action=echo, args_mapping=args, outputs_mapping=output,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [{"source": 7}, {"source.count": 2}, {}])
async def test_whole_argument_failures_use_normal_workflow_errors(
    values: dict[str, object],
) -> None:
    """Wrong records, missing fields and absent variables stop the action."""
    source = wf.define_variable[Record[int]]("source")
    task = wf.define_task("root", "Root", task_action=echo, args_mapping=source.quote)
    async with lclang.define_frame(preset=values) as frame:
        result = await wf.define_workflow("Records", task).execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        assert not result.task_args


@pytest.mark.asyncio
async def test_wrong_whole_context_output_is_rejected() -> None:
    """Context output annotations do not replace validation of the yielded object."""
    @asynccontextmanager
    async def wrong_resource(
        context: wf.TaskContext, args: Record[int], status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncIterator[Record[int]]:
        yield cast(Record[int], object())

    source = wf.define_variable[Record[int]]("source")
    target = wf.define_variable[Record[int]]("target")
    context = wf.define_context_task(
        "resource", "Resource", wrong_resource, source.quote, target.quote,
    )
    task = wf.define_task("root", "Root", context_tasks=[context])
    async with lclang.define_frame(preset={"source": Record(1)}) as frame:
        result = await wf.define_workflow("Records", task).execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        assert not frame.has("target")


@pytest.mark.asyncio
async def test_non_record_action_return_retains_boundary_error() -> None:
    """An action with no output mapping must still return a dataclass."""
    async def scalar(
        context: wf.TaskContext, args: Record[int], status_mgr: wf.ExecutionStatusManager,
    ) -> int:
        return args.value

    source = wf.define_variable[Record[int]]("source")
    task = wf.define_task("root", "Root", task_action=scalar, args_mapping=source.quote)
    async with lclang.define_frame(preset={"source": Record(1)}) as frame:
        result = await wf.define_workflow("Records", task).execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        assert not result.task_outputs
        error = await frame.get("__exception__")
        assert isinstance(error, wf.WorkflowException)
        assert "annotated dataclass" in str(error.exception)


@dataclass
class Empty:
    """An empty dataclass is still a valid whole record."""


async def empty_action(
    context: wf.TaskContext, args: Empty, status_mgr: wf.ExecutionStatusManager,
) -> Empty:
    """Return the empty record."""
    return args


@pytest.mark.asyncio
async def test_empty_records_support_verbose_scope_publication() -> None:
    """An empty scope update publishes no fields and produces no logging failure."""
    source = wf.define_variable[Empty]("source")
    target = wf.define_variable[Empty]("target")
    task = wf.define_task(
        "root", "Root", task_action=empty_action,
        args_mapping=source.quote, outputs_mapping=target.quote,
    )
    async with lclang.define_frame(
        preset={"source": Empty(), "target": lclang.FRAME_PROXY},
    ) as frame:
        result = await wf.define_workflow("Empty", task).execute(execution_context(frame, True))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        proxy = await frame.get("target")
        assert isinstance(proxy, lclang.FrameProxy)
        assert await proxy.field_names() == []


@pytest.mark.asyncio
async def test_scope_field_masks_and_target_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Field-level masks survive record logging and failed targets publish nothing."""
    source = wf.define_variable[Record[int]]("source")
    target = wf.define_variable[Record[int]]("target")
    task = wf.define_task(
        "root", "Root", task_action=echo,
        args_mapping=source.quote, outputs_mapping=target.quote,
    )
    module = lclang.define_module("records", {"source.value!": "314159", "target": "1 / 0"})
    workflow = wf.define_workflow("Records", task)
    async with lclang.define_frame(module) as frame:
        with caplog.at_level(logging.DEBUG, logger="record-mappings"):
            result = await workflow.execute(execution_context(frame, True))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        assert not frame.has("target.value")
    messages = [message for message in caplog.messages if message.startswith("args mapping:")]
    assert "*masked*" in messages[0] and "314159" not in messages[0]
