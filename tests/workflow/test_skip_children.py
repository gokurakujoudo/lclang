"""Action-directed child omission without synthetic skipped status records."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

import pytest

import lclang
import lclang.workflow as wf


@dataclass
class Value:
    """One mapped action value."""

    value: int = 0


def execution_context(frame: lclang.Frame) -> wf.WorkflowExecutionContext:
    """Return execution metadata with in-memory logging only."""
    return wf.WorkflowExecutionContext(
        False, date(2026, 9, 21), False, logging.getLogger("skip-children"), frame,
    )


def status_names(tree: wf.ExecutionStatusTree) -> list[str]:
    """Flatten names to detect records anywhere in the status tree."""
    return [tree.task_name, *(name for child in tree.sub_tasks for name in status_names(child))]


async def echo(
    context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
) -> Value:
    """Return the action arguments unchanged."""
    return args


@pytest.mark.asyncio
@pytest.mark.parametrize("omit", [False, True])
async def test_omission_preserves_outputs_steps_cleanup_and_siblings(
    omit: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the selected subtree disappears; current work and siblings remain."""
    events: list[str] = []
    captured: list[wf.TaskContext] = []

    @asynccontextmanager
    async def resource(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncIterator[Value]:
        with pytest.raises(RuntimeError, match="action"):
            context.skip_children()
        events.append(f"enter{args.value}")
        try:
            yield args
        finally:
            with pytest.raises(RuntimeError, match="action"):
                context.skip_children()
            events.append(f"exit{args.value}")

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        captured.append(context)
        if omit:
            context.skip_children()
            context.skip_children()
        status_mgr.add_step("own_step", "Keep this step", wf.ExecutionStatus.SUCCESS)
        events.append("action")
        return Value(17)

    child_input = wf.define_variable[int]("child_input")
    output = wf.define_variable[int]("published")
    nested_context = wf.define_context_task("child_context", "Child context", resource, Value(3))
    descendant = wf.define_task("descendant", "Descendant", task_action=echo, args_mapping=Value())
    child = wf.define_task(
        "child", "Child", task_action=echo, args_mapping=Value(child_input.quote),
        context_tasks=[nested_context], children=[descendant],
    )
    parent = wf.define_task(
        "parent", "Parent", task_action=action, args_mapping=Value(),
        outputs_mapping=Value(output.quote), children=[child],
        context_tasks=[
            wf.define_context_task("outer", "Outer", resource, Value(1)),
            wf.define_context_task("inner", "Inner", resource, Value(2)),
        ],
    )
    sibling = wf.define_task(
        "sibling", "Sibling", task_action=echo, args_mapping=Value(output.quote),
    )
    root = wf.define_task("root", "Root", children=[parent, sibling])
    workflow = wf.define_workflow("Workflow", root)
    assert "descendant" in "\n".join(workflow.to_lines())
    assert [p.name for p in workflow.to_cli("run", "Run").parameter_docs] == ["child_input"]
    async with lclang.define_frame(preset={} if omit else {"child_input": 1}) as frame:
        with caplog.at_level(logging.INFO, logger="skip-children"):
            result = await workflow.execute(execution_context(frame))
        assert await frame.get("published") == 17
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    names = status_names(result.execution_status)
    assert "own_step" in names and "sibling" in names
    assert ("child" in names) is not omit
    assert ("descendant" in names) is not omit
    assert ("child_context" in names) is not omit
    assert result.task_args[wf.TaskID("sibling")] == Value(17)
    if omit:
        assert set(result.task_args) == {"parent", "sibling"}
        assert set(result.task_outputs) == {"parent", "sibling"}
        assert events == ["enter1", "enter2", "action", "exit2", "exit1"]
        assert not any("root.parent.child" in message for message in caplog.messages)
    for context in captured:
        with pytest.raises(RuntimeError, match="action"):
            context.skip_children()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["raise", "status", "publication", "exit", "covered", "cancel"])
async def test_omission_survives_failures_and_cancellation(
    failure: str, caplog: pytest.LogCaptureFixture,
) -> None:
    """Error-path bookkeeping never reinserts a deliberately omitted child."""
    managers: list[wf.ExecutionStatusManager] = []
    captured: list[wf.TaskContext] = []
    events: list[str] = []

    @asynccontextmanager
    async def resource(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncIterator[Value]:
        try:
            yield args
        except ValueError:
            assert failure == "covered"
            status_mgr.update(wf.ExecutionStatus.FAILURE_COVERED)
        finally:
            events.append("cleanup")
            if failure == "exit":
                raise RuntimeError("cleanup failed")

    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        managers.append(status_mgr)
        captured.append(context)
        context.skip_children()
        if failure in {"raise", "covered"}:
            raise ValueError("action failed")
        if failure == "status":
            status_mgr.update(wf.ExecutionStatus.FAILURE)
        if failure == "cancel":
            raise asyncio.CancelledError
        return args

    output = wf.define_variable[Value]("output")
    child = wf.define_task("child", "Child", children=[wf.define_task("descendant", "Descendant")])
    parent = wf.define_task(
        "parent", "Parent", task_action=action, args_mapping=Value(),
        outputs_mapping=output.quote if failure == "publication" else None,
        context_tasks=[wf.define_context_task("resource", "Resource", resource, Value())],
        children=[child],
    )
    root = wf.define_task("root", "Root", children=[parent, wf.define_task("sibling", "Sibling")])
    workflow = wf.define_workflow("Workflow", root)
    module = lclang.define_module("config", {"output": "1 / 0"})
    async with lclang.define_frame(module) as frame:
        with caplog.at_level(logging.INFO, logger="skip-children"):
            if failure == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await workflow.execute(execution_context(frame))
            else:
                result = await workflow.execute(execution_context(frame))
                assert result.execution_status.status is (
                    wf.ExecutionStatus.FAILURE_COVERED if failure == "covered"
                    else wf.ExecutionStatus.FAILURE if failure == "status"
                    else wf.ExecutionStatus.ERROR
                )
                sibling_status = result.execution_status.sub_tasks[0].sub_tasks[1].status
                assert sibling_status is wf.ExecutionStatus.SKIPPED
                assert "child" not in result.task_args and "child" not in result.task_outputs
    assert events == ["cleanup"]
    assert "child" not in status_names(managers[0].current)
    assert "descendant" not in status_names(managers[0].current)
    assert not any("root.parent.child" in message for message in caplog.messages)
    with pytest.raises(RuntimeError, match="action"):
        captured[0].skip_children()


@pytest.mark.asyncio
async def test_skip_control_is_per_execution_and_allows_leaf_tasks() -> None:
    """Concurrent and repeated runs never mutate the shared task definition."""
    async def action(
        context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        if args.value:
            context.skip_children()
        await asyncio.sleep(0)
        return args

    source = wf.define_variable[int]("source")
    task = wf.define_task(
        "root", "Root", task_action=action, args_mapping=Value(source.quote),
        children=[wf.define_task("child", "Child")],
    )
    workflow = wf.define_workflow("Concurrent", task)

    async def run(omit: int) -> None:
        async with lclang.define_frame(preset={"source": omit}) as frame:
            result = await workflow.execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert ("child" in status_names(result.execution_status)) is not bool(omit)

    await asyncio.gather(*(run(index % 2) for index in range(24)))
    await run(0)
    leaf = wf.define_task("leaf", "Leaf", task_action=action, args_mapping=Value(1))
    async with lclang.define_frame() as frame:
        result = await wf.define_workflow("Leaf", leaf).execute(execution_context(frame))
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert not result.execution_status.sub_tasks[0].sub_tasks
