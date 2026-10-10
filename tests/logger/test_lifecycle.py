"""Cancellation, caller attribution and stdlib restoration contracts."""

import asyncio
import io
import logging
import threading
import warnings
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from lclang.error import LclErrorGroup, LclLoggerError, LclStateError, LclValidationError
from lclang.logger import use_logger, use_logger_handler
from lclang.logger.context import LoggerRuntime, current_runtime
from lclang.logger.logger import Logger
from lclang.logger.metrics import Counters
from lclang.logger.queue_handler import LocalQueueHandler
from lclang.logger.takeover import LoggingTakeover


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["stop", "join", "restore", "close"])
async def test_body_and_cleanup_failures_release_logging_scope(phase: str) -> None:
    """Every cleanup stage retains its cause after restoring ownership and stopping work."""
    body, cleanup = ValueError("body"), OSError("cleanup")
    original_handlers = logging.root.handlers
    original_stop = LocalQueueHandler.stop
    original_restore = LoggingTakeover.restore
    original_close = LocalQueueHandler.close

    def stop(handler: LocalQueueHandler) -> None:
        original_stop(handler)
        raise cleanup

    def restore(takeover: LoggingTakeover) -> None:
        original_restore(takeover)
        raise cleanup

    def close(handler: LocalQueueHandler) -> None:
        original_close(handler)
        raise cleanup

    runtime: LoggerRuntime | None = None
    with ExitStack() as patches, pytest.raises(LclErrorGroup) as caught:
        async with use_logger_handler({"console": {"enabled": False}}) as runtime:
            original_join = runtime.thread.join

            def join() -> None:
                original_join()
                raise cleanup

            target, name, replacement = {
                "stop": (LocalQueueHandler, "stop", stop),
                "join": (runtime.thread, "join", join),
                "restore": (LoggingTakeover, "restore", restore),
                "close": (LocalQueueHandler, "close", close),
            }[phase]
            # Keep the patch active while the owner performs its teardown.
            patches.enter_context(patch.object(target, name, replacement))
            raise body
    assert runtime is not None
    assert caught.value.code == "LCL622911"
    assert [error.__cause__ for error in caught.value.exceptions] == [body, cleanup]
    assert not runtime.thread.is_alive() and not runtime.started
    assert logging.root.handlers is original_handlers
    async with use_logger_handler({"console": {"enabled": False}}):
        await use_logger()


@pytest.mark.asyncio
async def test_writer_startup_control_signal_keeps_original_identity() -> None:
    """A startup control signal returns from the writer to its process scope owner."""
    signal = SystemExit(2)
    with (
        patch("lclang.logger.dispatcher.ConsoleSink", side_effect=signal),
        pytest.raises(SystemExit) as caught,
    ):
        async with use_logger_handler({}):
            raise AssertionError("startup must not enter the body")
    assert caught.value is signal


@pytest.mark.asyncio
async def test_cleanup_cancellation_and_native_failure_are_both_retained() -> None:
    """Join failures accompanying cancellation retain the native signal and cleanup cause."""
    from lclang.logger.api import finish_cleanup

    entered, finish = asyncio.Event(), asyncio.Event()
    native = OSError("join failed")

    async def operation() -> None:
        entered.set()
        await finish.wait()
        raise native

    task = asyncio.create_task(finish_cleanup(operation()))
    await entered.wait()
    task.cancel("cancel cleanup")
    await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError) as caught:
        await task
    assert caught.value.__cause__ is not None
    assert caught.value.__cause__.__cause__ is native


@pytest.mark.asyncio
async def test_caller_levels_options_and_scope_reuse() -> None:
    """Logger methods select the actual caller and follow sequential process scopes."""
    stream = io.StringIO()
    config = {"format": "%(funcName)s %(message)s", "console": {"stream": stream, "level": 0}}
    async with use_logger_handler(config):
        logger = await use_logger(name="example", prefix="[P]", emit_level=1)
        assert logger.name == "example" and logger.isEnabledFor(logging.INFO)

        def business_wrapper() -> None:
            logger.critical("critical")

        business_wrapper()
        direct = await use_logger()
        direct.log(logging.INFO, "direct", extra={"sample": 1})
        direct.warning("warning")
        direct.error("error")
        direct.debug("debug")
        direct.exception("no traceback", exc_info=False)
        for kwargs in ({"name": 1}, {"prefix": 1}, {"emit_level": -1}, {"emit_level": True}):
            # Invalid arguments intentionally exercise the untyped caller boundary.
            with pytest.raises((LclValidationError, LclValidationError)):
                await use_logger(**kwargs)  # pyright: ignore[reportArgumentType]
    assert "test_caller_levels_options_and_scope_reuse [P] critical" in stream.getvalue()
    assert "test_caller_levels_options_and_scope_reuse direct" in stream.getvalue()
    async with use_logger_handler(config):
        logger.info("reused")
    assert "[P] reused" in stream.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("preexisting_capture", [False, True])
async def test_takeover_warnings_and_exact_restoration(preexisting_capture: bool) -> None:
    """Named handlers, filters, disabled state and existing warning capture survive."""
    stream = io.StringIO()
    target = logging.getLogger("takeover.test")
    old = target.handlers, target.level, target.propagate, target.disabled, target.filters
    borrowed = logging.StreamHandler(io.StringIO())
    target.handlers, target.level, target.propagate, target.disabled = [borrowed], 50, False, True
    target.filters = [logging.Filter("unmatched")]
    expected = target.handlers, target.filters
    logging.captureWarnings(preexisting_capture)
    warning_callback = warnings.showwarning
    try:
        async with use_logger_handler(
            {
                "console": {"stream": stream},
                "capture_warnings": True,
                "takeover_loggers": ("takeover.test", "takeover.test", "root"),
            }
        ):
            target.warning("third-party")
            with warnings.catch_warnings():
                warnings.simplefilter("always")
                warnings.warn("captured-warning", UserWarning, stacklevel=1)
        assert "third-party" in stream.getvalue() and "captured-warning" in stream.getvalue()
        assert target.handlers is expected[0] and target.filters is expected[1]
        assert target.level == 50 and not target.propagate and target.disabled
        assert warnings.showwarning is warning_callback
        borrowed.emit(logging.makeLogRecord({"msg": "still usable"}))
    finally:
        target.handlers, target.level, target.propagate, target.disabled, target.filters = old
        logging.captureWarnings(False)
        borrowed.close()


@pytest.mark.asyncio
async def test_cancelled_exit_waits_for_drain_and_drops_late_records() -> None:
    """Repeated cancellation cannot restore handlers while accepted output is pending."""
    writing, unblock = threading.Event(), threading.Event()
    stream = io.StringIO()
    original = logging.root.handlers

    class SlowMessage:
        def __str__(self) -> str:
            writing.set()
            assert unblock.wait(5)
            return "accepted"

    async def application() -> None:
        async with use_logger_handler({"console": {"stream": stream}}):
            logger = await use_logger()
            logger.info(SlowMessage())

    task = asyncio.create_task(application())
    await asyncio.to_thread(writing.wait, 5)
    runtime = current_runtime()
    try:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert not task.done() and logging.root.handlers is not original
        awaitable_logger = Logger(None, "", 0)
        assert not awaitable_logger.isEnabledFor(20)
        awaitable_logger.info("late")
        runtime.handler.emit(logging.makeLogRecord({"msg": "late raw"}))
        with pytest.raises(LclStateError, match="closing"):
            await use_logger()
    finally:
        unblock.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert logging.root.handlers is original
    assert "accepted" in stream.getvalue() and "late" not in stream.getvalue()
    assert runtime.metrics.records_written == 1


@pytest.mark.asyncio
async def test_startup_thread_failure_and_body_failure_release_scope() -> None:
    """Failure before launch and an exceptional body both restore scope availability."""
    with (
        patch("lclang.logger.context.Thread.start", side_effect=RuntimeError("start failed")),
        pytest.raises(LclLoggerError, match="start failed"),
    ):
        async with use_logger_handler({}):
            pass
    with pytest.raises(ValueError, match="body"):
        async with use_logger_handler({"console": {"enabled": False}}):
            raise ValueError("body")
    async with use_logger_handler({"console": {"enabled": False}}):
        await use_logger()


def test_queue_filters_can_replace_records_and_stop_is_idempotent() -> None:
    """Handler filters preserve stdlib replacement semantics before queue snapshots."""
    handler = LocalQueueHandler(0, Counters())
    original = logging.makeLogRecord({"msg": "original"})
    handler.addFilter(lambda record: False)
    assert not handler.handle(original)
    handler.filters.clear()
    handler.addFilter(lambda record: logging.makeLogRecord({"msg": "replacement"}))
    assert handler.handle(original)
    handler.stop()
    handler.stop()
    queued = handler.queue.get()
    assert queued is not None and queued.msg == "replacement" and original.msg == "original"
    assert handler.queue.get() is None
    handler.close()
