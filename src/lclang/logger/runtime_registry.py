"""Process-wide exclusive runtime reservation and diagnostic ownership.

Defines ``LoggerRuntime``, ``reserve``, ``release``, ``current_runtime``.
"""

from __future__ import annotations

# Existing uppercase names denote mutable process state, not constants.
# pyright: reportConstantRedefinition=false
import os
from threading import Lock, Thread

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclStateError, LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.config_validation import level
from lclang.logger.handler_config import LoggerHandlerConfig
from lclang.logger.logging_metrics import Counters, RuntimeMetrics
from lclang.logger.queue_handler import LocalQueueHandler
from lclang.logger.sink_dispatcher import Dispatcher


@guard_constructor(LclValidationError, LoggerErrorCode.E21_LOGGER_RUNTIME_NATIVE_FAILURE)
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
    @guard_failure(LclLoggerError, LoggerErrorCode.E21_LOGGER_RUNTIME_NATIVE_FAILURE)
    def metrics(self) -> RuntimeMetrics:
        """Read detached diagnostics, including after the scope has closed.

        :returns: Immutable counters and paths.
        """
        return self.counters.snapshot()


# Unitless exclusive runtime slot and lock protect scope ownership, not task-local logging state.
RUNTIME_LOCK = Lock()
ACTIVE_RUNTIME: LoggerRuntime | None = None


@guard_failure(LclLoggerError, LoggerErrorCode.E21_LOGGER_RUNTIME_NATIVE_FAILURE)
def reserve(runtime: LoggerRuntime) -> None:
    """Reject overlapping scopes before any writer is launched.

    :param runtime: Proposed process-local runtime.
    :raises LclStateError: If an active or inherited runtime already exists.
    """
    global ACTIVE_RUNTIME
    with RUNTIME_LOCK:
        if ACTIVE_RUNTIME is not None:
            raise LclStateError(
                "only one logger handler scope is allowed per process; initialize after fork",
                code=LoggerErrorCode.E21_ONLY_ONE_LOGGER_HANDLER_SCOPE_IS_ALLOWED_PER_PROCESS_INITIALIZE_A,
            )
        ACTIVE_RUNTIME = runtime


@guard_failure(LclLoggerError, LoggerErrorCode.E21_LOGGER_RUNTIME_NATIVE_FAILURE)
def release() -> None:
    """Release the slot only after complete writer cleanup and state restoration."""
    global ACTIVE_RUNTIME
    with RUNTIME_LOCK:
        ACTIVE_RUNTIME = None


@guard_failure(LclLoggerError, LoggerErrorCode.E21_LOGGER_RUNTIME_NATIVE_FAILURE)
def current_runtime() -> LoggerRuntime:
    """Find a usable runtime across all threads and async tasks in this process.

    :returns: Current process runtime, possibly draining.
    :raises LclStateError: If no initialized scope exists or fork inherited it.
    """
    runtime = ACTIVE_RUNTIME
    if runtime is None or runtime.pid != os.getpid() or not runtime.started:
        raise LclStateError(
            "use_logger requires an active use_logger_handler scope",
            code=LoggerErrorCode.E21_USE_LOGGER_REQUIRES_AN_ACTIVE_USE_LOGGER_HANDLER_SCOPE,
        )
    return runtime
