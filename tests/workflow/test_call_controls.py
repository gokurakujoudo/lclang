"""Dynamic calls retain native control groups while closing their owned Frames."""

import pytest

from lclang.lang import Frame, define_frame
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    TaskContext,
    Workflow,
    WorkflowExecutionContext,
    WorkflowExecutionResult,
)
from tests.workflow.call_support import Value, make_child, run_parent


@pytest.mark.asyncio
async def test_unexpected_child_control_group_never_yields_an_error_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A control group cannot become a recoverable child ERROR result."""
    signal = StopAsyncIteration("done")
    ordinary = OSError("business")
    original = ExceptionGroup("control", [signal, ordinary])
    child = make_child()
    execute = Workflow.execute
    owned: list[Frame] = []

    async def fail(self: Workflow, context: WorkflowExecutionContext) -> WorkflowExecutionResult:
        if self is child:
            owned.append(context.frame)
            raise original
        return await execute(self, context)

    monkeypatch.setattr(Workflow, "execute", fail)

    async def parent(context: TaskContext, manager: ExecutionStatusManager) -> Value:
        with pytest.raises(ExceptionGroup) as caught:
            async with child.execute_in_task(context, manager, name="control"):
                pytest.fail("control group must not yield a child result")
        assert caught.value is original and original.exceptions == (signal, ordinary)
        assert owned[0].closed and not context.frame.closed
        assert manager.current.sub_tasks[0].status is ExecutionStatus.ERROR
        return Value(1)

    async with define_frame(preset={"alive": 1}) as frame:
        result = await run_parent(parent, frame)
        assert await frame.get("alive") == 1
    assert result.execution_status.status is ExecutionStatus.ERROR
