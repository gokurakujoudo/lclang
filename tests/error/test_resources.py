"""Execution, cleanup, cancellation, and constructor failure boundary contracts."""

import asyncio
from collections.abc import Awaitable
from typing import cast

import pytest

from lclang.common.source_location import UNKNOWN_SPAN
from lclang.error import LclError, LclErrorGroup, LclEvaluationError, LclValidationError
from lclang.error.cleanup_wait import settle_cleanup
from lclang.error.diagnostic_records import ConfigLoadFrame
from lclang.error.failure_aggregation import combine_failures
from lclang.error.loading_context import derive_loading_error
from lclang.lang import define_frame, define_module
from tests.lang.evaluator.context_support import SyncManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [LclValidationError("known", code="APP"), asyncio.CancelledError("stop"), SystemExit(2)],
)
async def test_raise_expression_retains_lcl_codes_and_native_control_identity(
    error: BaseException,
) -> None:
    """Raising an existing structured error or control signal preserves that object."""
    async with define_frame(preset={"error": error}) as frame:
        with pytest.raises(type(error)) as caught:
            await frame.evaluate("raise(error)")
    assert caught.value is error


@pytest.mark.asyncio
@pytest.mark.parametrize("source,code", [("fail()", "LCL132811"), ("raise(error)", "LCL136962")])
async def test_native_groups_keep_protocol_through_evaluation(source: str, code: str) -> None:
    """A host call and an explicit raise both retain native grouped causes and members."""
    original = ExceptionGroup("business", [OSError("first"), ValueError("second")])

    def fail() -> None:
        raise original

    async with define_frame(preset={"fail": fail, "error": original}) as frame:
        with pytest.raises(LclErrorGroup) as caught:
            await frame.evaluate(source)
    assert caught.value.code == code and caught.value.__cause__ is original
    assert [item.__cause__ for item in caught.value.exceptions] == list(original.exceptions)


def test_compatibility_paths_reexport_the_central_error_types() -> None:
    """Supported historical import paths expose the same centralized class objects."""
    from lclang.error import CalendarLogicException
    from lclang.error import CalendarLogicException as HistoricalCalendar
    from lclang.error import ConfigLoadFrame as HistoricalContext
    from lclang.error import LclError as HistoricalError

    assert HistoricalError is LclError
    assert HistoricalContext is ConfigLoadFrame
    assert HistoricalCalendar is CalendarLogicException


@pytest.mark.parametrize("signal", [StopIteration(), StopAsyncIteration()])
def test_error_constructor_preserves_iterator_protocol_signals(signal: Exception) -> None:
    """Application exception constructors retain native iterator termination."""

    class IteratorError(LclError):
        def __init__(self) -> None:
            raise signal

    with pytest.raises(type(signal)) as caught:
        IteratorError()
    assert caught.value is signal
    assert combine_failures(None, signal) is signal
    assert combine_failures(signal, signal) is signal
    with pytest.raises(LclValidationError) as invalid:
        LclErrorGroup("invalid control member", [signal])
    assert invalid.value.code == "LCL021111"


def test_control_cleanup_takes_priority_and_loading_retains_native_spans() -> None:
    """Cleanup control identity survives and native loading retains attached source."""
    ordinary = ValueError("body")
    signal = KeyboardInterrupt("cleanup")
    assert combine_failures(ordinary, signal) is signal
    assert signal.__cause__ is not None and signal.__cause__.__cause__ is ordinary
    vars(ordinary)["source_span"] = UNKNOWN_SPAN
    loaded = derive_loading_error(ordinary, ConfigLoadFrame(UNKNOWN_SPAN.origin))
    assert loaded.code == "LCL323891" and loaded.span is UNKNOWN_SPAN
    assert loaded.__cause__ is ordinary


@pytest.mark.asyncio
async def test_settled_cleanup_classifies_setup_and_waits_through_cancellation() -> None:
    """Invalid awaitables fail safely and repeated cancellation cannot abandon cleanup."""
    invalid = await settle_cleanup(cast(Awaitable[None], None))
    assert isinstance(invalid, LclError) and isinstance(invalid.__cause__, TypeError)
    entered, finish = asyncio.Event(), asyncio.Event()
    native = OSError("close failed")

    async def close() -> None:
        entered.set()
        await finish.wait()
        raise native

    task = asyncio.create_task(settle_cleanup(close()))
    await entered.wait()
    task.cancel("first")
    await asyncio.sleep(0)
    task.cancel("second")
    await asyncio.sleep(0)
    assert not task.done()
    finish.set()
    retained = await task
    assert isinstance(retained, asyncio.CancelledError)
    cause = cast(BaseExceptionGroup[BaseException], retained.__cause__)
    assert isinstance(cause, BaseExceptionGroup)
    leaves = cause.exceptions
    assert any(isinstance(item, LclError) and item.__cause__ is native for item in leaves)


@pytest.mark.asyncio
async def test_frame_body_and_all_resource_failures_preserve_cause_and_state() -> None:
    """A Frame closes every cached resource and retains the body and both close failures."""
    events: list[str] = []
    first, second, body = OSError("first"), OSError("second"), ValueError("body")

    class Resource:
        def __init__(self, name: str, error: Exception) -> None:
            self.name, self.error = name, error

        async def aclose(self) -> None:
            events.append(self.name)
            raise self.error

    resources = Resource("first", first), Resource("second", second)
    frame = define_frame(
        define_module("resources", {"first": "make_first()", "second": "make_second()"}),
        preset={"make_first": lambda: resources[0], "make_second": lambda: resources[1]},
    )
    with pytest.raises(LclErrorGroup) as caught:
        async with frame:
            assert await frame.get("first") is resources[0]
            assert await frame.get("second") is resources[1]
            raise body
    assert caught.value.code == "LCL236912"
    assert caught.value.exceptions[0].__cause__ is body
    cleanup = caught.value.exceptions[1]
    assert isinstance(cleanup, LclErrorGroup) and cleanup.code == "LCL236911"
    assert [error.__cause__ for error in cleanup.exceptions] == [second, first]
    assert events == ["second", "first"] and frame.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["enter", "exit", "both", "control"])
async def test_expression_context_failures_keep_codes_and_unwind(phase: str) -> None:
    """Context boundaries retain existing LCL errors and combine execution with cleanup."""
    events: list[str] = []
    existing = LclEvaluationError("business", code="APP")
    cleanup = OSError("exit")
    signal = asyncio.CancelledError("stop")
    manager = SyncManager(
        "resource",
        events,
        enter_error=existing if phase == "enter" else None,
        exit_error=cleanup if phase in {"both", "control"} else existing,
    )
    source = "with resource: 1 / 0" if phase == "both" else "with resource: stop()"

    def stop() -> int:
        if phase == "control":
            raise signal
        return 1

    async with define_frame(
        define_module("context", {"result": source}), preset={"resource": manager, "stop": stop}
    ) as frame:
        if phase == "control":
            with pytest.raises(asyncio.CancelledError) as cancelled:
                await frame.evaluate(source)
            assert cancelled.value is signal and signal.__cause__ is not None
            assert signal.__cause__.__cause__ is cleanup
        elif phase == "both":
            with pytest.raises(LclErrorGroup) as combined:
                await frame.get("result")
            assert combined.value.code == "LCL138911"
            assert all(isinstance(error, LclError) for error in combined.value.exceptions)
            assert [cast(LclError, error).code for error in combined.value.exceptions] == [
                "LCL131421",
                "LCL138812",
            ]
            assert combined.value.exceptions[1].__cause__ is cleanup
        else:
            with pytest.raises(LclEvaluationError) as caught:
                await frame.get("result")
            assert caught.value is existing and caught.value.code == "APP"
    assert events == (
        ["enter resource"] if phase == "enter" else ["enter resource", "exit resource"]
    )


@pytest.mark.asyncio
async def test_expression_exit_and_finalizer_have_distinct_failure_codes() -> None:
    """A successful body can fail on exit and two failed forms produce a group."""
    native = OSError("exit")
    manager = SyncManager("resource", [], exit_error=native)
    async with define_frame(
        define_module(
            "forms",
            {"exit": "with resource: 1", "finally": 'try: raise("body") finally: raise("cleanup")'},
        ),
        preset={"resource": manager},
    ) as frame:
        with pytest.raises(LclEvaluationError) as exit_failure:
            await frame.get("exit")
        assert exit_failure.value.code == "LCL138812" and exit_failure.value.__cause__ is native
        with pytest.raises(LclErrorGroup) as finalizer:
            await frame.get("finally")
        assert finalizer.value.code == "LCL136963"
        assert all(isinstance(error, LclError) for error in finalizer.value.exceptions)
        assert [cast(LclError, error).code for error in finalizer.value.exceptions] == [
            "LCL136962",
            "LCL136962",
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,code,cause",
    [
        ("1 << -1", "LCL139811", ValueError),
        ("values[9]", "LCL133313", IndexError),
        ("1e308 ** 2", "LCL131422", OverflowError),
    ],
)
async def test_known_native_operator_reasons_are_classified(
    source: str, code: str, cause: type[Exception]
) -> None:
    """The operation and native type determine codes without inspecting message text."""
    async with define_frame(
        define_module("operators", {"result": source}), preset={"values": []}
    ) as frame:
        with pytest.raises(LclEvaluationError) as caught:
            await frame.get("result")
        assert caught.value.code == code and isinstance(caught.value.__cause__, cause)
