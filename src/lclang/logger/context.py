"""Process-wide exclusive runtime reservation and diagnostic ownership."""

from __future__ import annotations

# Existing uppercase names denote mutable process state, not constants.
# pyright: reportConstantRedefinition=false
import os
from threading import Lock, Thread

from lclang.logger.config import LoggerHandlerConfig
from lclang.logger.dispatcher import Dispatcher
from lclang.logger.metrics import Counters, RuntimeMetrics
from lclang.logger.queue_handler import LocalQueueHandler
from lclang.logger.validation import level


class LoggerRuntime:
    """Own one queue, dispatcher, and immutable metric snapshots."""

    def __init__(self, config: LoggerHandlerConfig) -> None:
        """Allocate process-local resources before starting any output.

        :param config: Validated immutable handler configuration.
        """
        self.pid = os.getpid()
        self.counters = Counters()
        self.handler = LocalQueueHandler(level(config.level, "logger.level"), self.counters)
        self.dispatcher = Dispatcher(config, self.handler.queue, self.counters)
        self.thread = Thread(target=self.dispatcher.run, name="lclang.logger.writer", daemon=True)
        self.started = False

    @property
    def metrics(self) -> RuntimeMetrics:
        """Read detached diagnostics, including after the scope has closed.

        :returns: Immutable counters and paths.
        """
        return self.counters.snapshot()


# Unitless exclusive runtime slot and lock protect scope ownership, not task-local logging state.
RUNTIME_LOCK = Lock()
ACTIVE_RUNTIME: LoggerRuntime | None = None


def reserve(runtime: LoggerRuntime) -> None:
    """Reject overlapping scopes before any writer is launched.

    :param runtime: Proposed process-local runtime.
    :raises RuntimeError: If an active or inherited runtime already exists.
    """
    global ACTIVE_RUNTIME
    with RUNTIME_LOCK:
        if ACTIVE_RUNTIME is not None:
            raise RuntimeError(
                "only one logger handler scope is allowed per process; initialize after fork"
            )
        ACTIVE_RUNTIME = runtime


def release() -> None:
    """Release the slot only after complete writer cleanup and state restoration."""
    global ACTIVE_RUNTIME
    with RUNTIME_LOCK:
        ACTIVE_RUNTIME = None


def current_runtime() -> LoggerRuntime:
    """Find a usable runtime across all threads and async tasks in this process.

    :returns: Current process runtime, possibly draining.
    :raises RuntimeError: If no initialized scope exists or fork inherited it.
    """
    runtime = ACTIVE_RUNTIME
    if runtime is None or runtime.pid != os.getpid() or not runtime.started:
        raise RuntimeError("use_logger requires an active use_logger_handler scope")
    return runtime
