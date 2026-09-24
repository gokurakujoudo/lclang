"""Dynamic workflow scopes finish owned cleanup before propagating cancellation."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest

import lclang
import lclang.workflow as wf
from tests.workflow.call_support import Value, install_call_resource, make_child, run_parent


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_cancellation_during_child_execution_unwinds_context_resources(
    fail_cleanup: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The active child scope unwinds before cancellation leaves the parent action."""
    entered = asyncio.Event()
    closed: list[str] = []

    class Resource:
        def close(self) -> None:
            closed.append("frame")
            if fail_cleanup:
                raise OSError("cleanup after cancelled execution")

    install_call_resource(monkeypatch, Resource)

    @asynccontextmanager
    async def resource(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncGenerator[Value]:
        try:
            yield args
        finally:
            closed.append("context")

    async def wait(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        await context.frame.get("resource")
        entered.set()
        await asyncio.Event().wait()
        return args

    child = wf.define_workflow(
        "Waiting",
        wf.define_task(
            "wait",
            "Wait",
            task_action=wait,
            args_mapping=Value(1),
            context_tasks=[
                wf.define_context_task("resource", "Resource", resource, Value(1)),
            ],
        ),
    )

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with child.execute_in_task(context, manager, name="waiting"):
            pytest.fail("cancelled child yielded")

    async with lclang.define_frame(preset={"alive": 1}) as frame, asyncio.timeout(5):
        running = asyncio.create_task(run_parent(parent, frame))
        await entered.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await running
        if fail_cleanup:
            assert caught.value.__cause__ is not None
        assert closed == ["context", "frame"]
        assert await frame.get("alive") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_repeated_cancellation_waits_for_final_owned_frame_cleanup(
    fail_cleanup: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even repeated cancellation cannot leave asynchronous Frame cleanup running behind."""
    entered = asyncio.Event()
    release = asyncio.Event()
    closed: list[str] = []
    results: list[wf.WorkflowExecutionResult] = []

    class Resource:
        async def aclose(self) -> None:
            entered.set()
            await release.wait()
            closed.append("frame")
            if fail_cleanup:
                raise OSError("cleanup failed")

    install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child().execute_in_task(
            context,
            manager,
            name="closing",
            preset={"input": 1},
        ) as result:
            results.append(result)
            await result.execution_frame.get("resource")
        return Value(1)

    async with lclang.define_frame() as frame, asyncio.timeout(5):
        running = asyncio.create_task(run_parent(parent, frame))
        await entered.wait()
        for _ in range(2):
            running.cancel()
            await asyncio.sleep(0)
        assert not running.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert closed == ["frame"]
        assert results[0].execution_status.status is wf.ExecutionStatus.ERROR
        assert results[0].task_outputs[wf.TaskID("child")] == Value(2)


@pytest.mark.asyncio
async def test_nonordinary_cleanup_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process-control exceptions are never normalized into business results."""

    class StopCall(BaseException):
        pass

    class Resource:
        def close(self) -> None:
            raise StopCall("stop")

    install_call_resource(monkeypatch, Resource)

    async def parent(context: wf.TaskContext, manager: wf.ExecutionStatusManager) -> Value:
        async with make_child().execute_in_task(
            context,
            manager,
            name="stop",
            preset={"input": 1},
        ) as result:
            await result.execution_frame.get("resource")
        return Value(1)

    async with lclang.define_frame() as frame:
        with pytest.raises(StopCall):
            await run_parent(parent, frame)
