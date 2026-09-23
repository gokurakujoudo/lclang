"""Repeated isolated workflow calls leave usable snapshots and release their Frames."""

import weakref

import pytest

import lclang
import lclang.workflow as wf
from lclang.runtime import Frame
from tests.workflow.call_support import Value, make_child, run_parent


@pytest.mark.asyncio
async def test_repeated_workflow_calls_release_frames_and_keep_detached_results() -> None:
    """One reusable definition can process a runtime-sized batch without retained Frames."""
    frames: list[weakref.ReferenceType[Frame]] = []
    outputs: list[object] = []
    child = make_child()

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        for index in range(150):
            async with child.execute_in_task(
                context, manager, name=f"item-{index}", preset={"input": index},
            ) as result:
                frames.append(weakref.ref(result.execution_frame))
                outputs.append(result.task_outputs[wf.TaskID("child")])
            assert result.execution_frame.closed
        return Value(len(outputs))

    async with lclang.define_frame() as frame:
        result = await run_parent(parent, frame)
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert result.task_outputs[wf.TaskID("parent")] == Value(150)
    assert outputs == [Value(index + 1) for index in range(150)]
    assert all(reference() is None for reference in frames)
    assert len(result.execution_status.sub_tasks[0].sub_tasks) == 150
