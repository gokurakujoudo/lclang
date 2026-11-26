"""Dynamic workflow scopes finish owned cleanup before propagating cancellation."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest

import lclang.workflow as wf
from lclang.error.failure_aggregation import contains_failure
from lclang.lang import define_frame
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
    cleanup_failure = OSError("cleanup after cancelled execution")
    captured: dict[str, wf.ExecutionStatusTree] = {}
    add_sub_task = wf.ExecutionStatusManager.add_sub_task

    def capture_sub_task(
        manager: wf.ExecutionStatusManager,
        name: str,
        description: str,
        status: wf.ExecutionStatus = wf.ExecutionStatus.PENDING,
    ) -> wf.ExecutionStatusManager:
        child_manager = add_sub_task(manager, name, description, status)
        captured[name] = child_manager.current
        return child_manager

    monkeypatch.setattr(wf.ExecutionStatusManager, "add_sub_task", capture_sub_task)

    class Resource:
        def close(self) -> None:
            closed.append("frame")
            if fail_cleanup:
                raise cleanup_failure

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

    async with define_frame(preset={"alive": 1}) as frame, asyncio.timeout(5):
        running = asyncio.create_task(run_parent(parent, frame))
        await entered.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await running
        if fail_cleanup:
            assert caught.value.__cause__ is not None
            assert contains_failure(caught.value.__cause__, cleanup_failure)
        else:
            for name in ("parent", "parent$action", "waiting"):
                assert captured[name].status is wf.ExecutionStatus.FAILURE
        assert closed == ["context", "frame"]
        assert await frame.get("alive") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_cleanup", [False, True])
async def test_repeated_cancellation_waits_for_final_owned_frame_cleanup(
    fail_cleanup: bool,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Even repeated cancellation cannot leave asynchronous Frame cleanup running behind."""
    entered = asyncio.Event()
    release = asyncio.Event()
    closed: list[str] = []
    results: list[wf.WorkflowExecutionResult] = []
    call_statuses: list[wf.ExecutionStatusTree] = []
    cleanup_failure = OSError("cleanup failed")

    class Resource:
        async def aclose(self) -> None:
            entered.set()
            await release.wait()
            closed.append("frame")
            if fail_cleanup:
                raise cleanup_failure

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
            call_statuses.append(manager.current.sub_tasks[-1])
        return Value(1)

    async with define_frame() as frame, asyncio.timeout(5):
        running = asyncio.create_task(run_parent(parent, frame))
        await entered.wait()
        for message in ("user-stop", "second-cancel"):
            running.cancel(message)
            await asyncio.sleep(0)
        assert not running.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await running
        assert caught.value.args == ("user-stop",)
        assert closed == ["frame"]
        await asyncio.sleep(0)
        assert not any(
            "exception in shielded future" in record.getMessage() for record in caplog.records
        )
        if fail_cleanup:
            assert call_statuses[0].status is wf.ExecutionStatus.ERROR
            assert caught.value.__cause__ is not None
            assert contains_failure(caught.value.__cause__, cleanup_failure)
        assert results[0].execution_status.status is wf.ExecutionStatus.SUCCESS
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

    async with define_frame() as frame:
        with pytest.raises(StopCall):
            await run_parent(parent, frame)
