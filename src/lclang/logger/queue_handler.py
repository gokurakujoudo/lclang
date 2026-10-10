"""Admission-ordered queue handler with no producer formatting or output.

Defines ``LocalQueueHandler``.
"""

from __future__ import annotations

import copy
import logging
from queue import SimpleQueue
from threading import RLock

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.logging_metrics import Counters


@guard_constructor(LclValidationError, LoggerErrorCode.E36_LOG_QUEUE_NATIVE_FAILURE)
class LocalQueueHandler(logging.Handler):
    """Accept shallow record snapshots until a sentinel is committed."""

    def __init__(self, threshold: int, counters: Counters) -> None:
        """Initialize only memory and synchronization primitives.

        :param threshold: Global minimum severity, also filtering propagated records.
        :param counters: Shared runtime diagnostics.
        """
        super().__init__(threshold)
        self.admission = RLock()
        self.queue: SimpleQueue[logging.LogRecord | None] = SimpleQueue()
        self.counters = counters
        self.closing = False

    @guard_failure(LclLoggerError, LoggerErrorCode.E36_LOG_QUEUE_NATIVE_FAILURE)
    def handle(self, record: logging.LogRecord) -> bool:
        """Use only the admission lock to avoid handler/admission lock inversion.

        :param record: Producer-created event.
        :returns: Whether filters accepted the event.
        """
        selected = self.filter(record)
        if selected:
            self.emit(selected if isinstance(selected, logging.LogRecord) else record)
        return bool(selected)

    @guard_failure(LclLoggerError, LoggerErrorCode.E36_LOG_QUEUE_NATIVE_FAILURE)
    def emit(self, record: logging.LogRecord) -> None:
        """Copy and enqueue without formatting the message or traceback.

        :param record: Producer-created stdlib event.
        """
        with self.admission:
            if not self.closing:
                self.queue.put(copy.copy(record))
                self.counters.add("records_enqueued")

    @guard_failure(LclLoggerError, LoggerErrorCode.E36_LOG_QUEUE_NATIVE_FAILURE)
    def stop(self) -> None:
        """Atomically end admission and place the sentinel after accepted events."""
        with self.admission:
            if not self.closing:
                self.closing = True
                self.queue.put(None)
