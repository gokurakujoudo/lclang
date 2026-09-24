"""Async scope entry and cancellation-resilient process logging teardown."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Mapping
from contextlib import asynccontextmanager

from lclang.logger.config import LoggerHandlerConfig, handler_config
from lclang.logger.context import LoggerRuntime, current_runtime, release, reserve
from lclang.logger.logger import Logger
from lclang.logger.takeover import LoggingTakeover


async def finish_cleanup(operation: Awaitable[None]) -> None:
    """Wait through repeated caller cancellation before propagating it.

    :param operation: Cleanup coroutine whose resources must finish closing.
    :raises CancelledError: After cleanup if the caller was cancelled while waiting.
    """
    task = asyncio.ensure_future(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


@asynccontextmanager
async def use_logger_handler(
    config: LoggerHandlerConfig | Mapping[str, object],
) -> AsyncGenerator[LoggerRuntime]:
    """Own one process-wide queue writer and restore logging after complete drain.

    :param config: Validated object or configuration mapping.
    :returns: Async context manager yielding read-only runtime diagnostics.
    :raises RuntimeError: If another scope exists or an inherited runtime is present.
    :raises BaseException: If startup or the scope body fails, after cleanup.
    """
    config = handler_config(config)
    runtime = LoggerRuntime(config)
    reserve(runtime)
    takeover: LoggingTakeover | None = None
    launched = False
    try:
        runtime.thread.start()
        launched = True
        await asyncio.to_thread(runtime.dispatcher.ready.wait)
        if runtime.dispatcher.startup_error is not None:
            raise runtime.dispatcher.startup_error
        takeover = LoggingTakeover(config, runtime.handler)
        takeover.install()
        runtime.started = True
        yield runtime
    finally:
        runtime.handler.stop()
        try:
            if launched:
                await finish_cleanup(asyncio.to_thread(runtime.thread.join))
        finally:
            with runtime.handler.admission:
                if takeover is not None:
                    takeover.restore()
                runtime.started = False
                runtime.handler.close()
                release()


async def use_logger(name: str | None = None, prefix: str = "", emit_level: int = 0) -> Logger:
    """Bind a source name, prefix and caller offset inside an active handler scope.

    :param name: Stdlib logger name; None selects root.
    :param prefix: Fixed first-line message prefix.
    :param emit_level: Additional application wrapper frames skipped by stacklevel.
    :returns: Lightweight scope-independent logger wrapper.
    :raises TypeError: If name or prefix is not text.
    :raises ValueError: If emit_level is not a nonnegative integer.
    :raises RuntimeError: If no initialized accepting scope exists.
    """
    runtime = current_runtime()
    if runtime.handler.closing:
        raise RuntimeError("logger handler scope is closing")
    if (name is not None and not isinstance(name, str)) or not isinstance(prefix, str):
        raise TypeError("logger name and prefix must be text")
    if type(emit_level) is not int or emit_level < 0:
        raise ValueError("emit_level must be a nonnegative integer")
    return Logger(name, prefix, emit_level)
