"""Async scope entry and cancellation-resilient process logging teardown."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Mapping
from contextlib import asynccontextmanager

from lclang.error import LclLoggerError
from lclang.error.aggregation import combine_failures
from lclang.error.base import LclStateError, LclValidationError
from lclang.error.boundary import guard_async_failure
from lclang.error.codes.logging import Code as logging_codes
from lclang.error.waiting import settle_cleanup
from lclang.error.wrapping import is_ordinary_failure, wrap_failure
from lclang.logger.config import LoggerHandlerConfig, handler_config
from lclang.logger.context import LoggerRuntime, current_runtime, release, reserve
from lclang.logger.logger import Logger
from lclang.logger.takeover import LoggingTakeover


@guard_async_failure(LclLoggerError, logging_codes.NATIVE_622)
async def finish_cleanup(operation: Awaitable[None]) -> None:
    """Wait through repeated caller cancellation before propagating it.

    :param operation: Cleanup coroutine whose resources must finish closing.
    :raises CancelledError: After cleanup if the caller was cancelled while waiting.
    """
    failure = await settle_cleanup(
        operation, error_type=LclLoggerError, code=logging_codes.CLEANUP_FAILURE
    )
    if failure is not None:
        raise failure from failure.__cause__


@asynccontextmanager
async def use_logger_handler(
    config: LoggerHandlerConfig | Mapping[str, object],
) -> AsyncGenerator[LoggerRuntime]:
    """Own one process-wide queue writer and restore logging after complete drain.

    :param config: Validated object or configuration mapping.
    :returns: Async context manager yielding read-only runtime diagnostics.
    :raises LclStateError: If another scope exists or an inherited runtime is present.
    :raises BaseException: If startup or the scope body fails, after cleanup.
    """
    config = handler_config(config)
    runtime = LoggerRuntime(config)
    reserve(runtime)
    takeover: LoggingTakeover | None = None
    launched = False
    pending: BaseException | None = None
    try:
        try:
            runtime.thread.start()
        except Exception as error:
            failure = wrap_failure(error, LclLoggerError, logging_codes.STARTUP_FAILURE)
            raise failure from failure.__cause__
        launched = True
        await asyncio.to_thread(runtime.dispatcher.ready.wait)
        if runtime.dispatcher.startup_error is not None:
            startup_error = runtime.dispatcher.startup_error
            if isinstance(startup_error, Exception):
                raise wrap_failure(startup_error, LclLoggerError, logging_codes.STARTUP_FAILURE)
            raise startup_error
        takeover = LoggingTakeover(config, runtime.handler)
        takeover.install()
        runtime.started = True
        yield runtime
    except BaseException as error:
        pending = error
    finally:
        try:
            try:
                runtime.handler.stop()
            except BaseException as error:
                pending = retain_cleanup_failure(pending, error)
                with runtime.handler.admission:
                    runtime.handler.closing = True
                    runtime.handler.queue.put(None)
            if launched:
                try:
                    await finish_cleanup(asyncio.to_thread(runtime.thread.join))
                except BaseException as error:
                    pending = retain_cleanup_failure(pending, error)
        finally:
            with runtime.handler.admission:
                if takeover is not None:
                    try:
                        takeover.restore()
                    except BaseException as error:
                        pending = retain_cleanup_failure(pending, error)
                runtime.started = False
                try:
                    runtime.handler.close()
                except BaseException as error:
                    pending = retain_cleanup_failure(pending, error)
                finally:
                    release()
    if pending is not None:
        raise pending from pending.__cause__


def retain_cleanup_failure(pending: BaseException | None, error: BaseException) -> BaseException:
    """Retain a logging cleanup failure alongside an already pending failure.

    :param pending: Scope execution failure or earlier cleanup failure.
    :param error: Failure of the current cleanup operation.
    :returns: Structured ordinary failure/group or unchanged native control signal.
    """
    cleanup = (
        wrap_failure(error, LclLoggerError, logging_codes.CLEANUP_FAILURE)
        if is_ordinary_failure(error)
        else error
    )
    return combine_failures(pending, cleanup, code=logging_codes.COMPOSITE_FAILURE)


@guard_async_failure(LclLoggerError, logging_codes.NATIVE_622)
async def use_logger(name: str | None = None, prefix: str = "", emit_level: int = 0) -> Logger:
    """Bind a source name, prefix and caller offset inside an active handler scope.

    :param name: Stdlib logger name; None selects root.
    :param prefix: Fixed first-line message prefix.
    :param emit_level: Additional application wrapper frames skipped by stacklevel.
    :returns: Lightweight scope-independent logger wrapper.
    :raises LclValidationError: If name or prefix is not text.
    :raises LclValidationError: If emit_level is not a nonnegative integer.
    :raises LclStateError: If no initialized accepting scope exists.
    """
    runtime = current_runtime()
    if runtime.handler.closing:
        raise LclStateError(
            "logger handler scope is closing",
            code=logging_codes.E22_LOGGER_HANDLER_SCOPE_IS_CLOSING,
        )
    if (name is not None and not isinstance(name, str)) or not isinstance(prefix, str):
        raise LclValidationError(
            "logger name and prefix must be text",
            code=logging_codes.E22_LOGGER_NAME_AND_PREFIX_MUST_BE_TEXT,
        )
    if type(emit_level) is not int or emit_level < 0:
        raise LclValidationError(
            "emit_level must be a nonnegative integer",
            code=logging_codes.E22_EMIT_LEVEL_MUST_BE_A_NONNEGATIVE_INTEGER,
        )
    return Logger(name, prefix, emit_level)
