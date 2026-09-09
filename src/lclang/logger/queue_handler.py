"""Admission-ordered queue handler with no producer formatting or output."""

from __future__ import annotations

import copy
import logging
from queue import SimpleQueue
from threading import RLock

from lclang.logger.metrics import Counters


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

    def handle(self, record: logging.LogRecord) -> bool:
        """Use only the admission lock to avoid handler/admission lock inversion.

        :param record: Producer-created event.
        :returns: Whether filters accepted the event.
        """
        selected = self.filter(record)
        if selected:
            self.emit(selected if isinstance(selected, logging.LogRecord) else record)
        return bool(selected)

    def emit(self, record: logging.LogRecord) -> None:
        """Copy and enqueue without formatting the message or traceback.

        :param record: Producer-created stdlib event.
        """
        with self.admission:
            if not self.closing:
                self.queue.put(copy.copy(record))
                self.counters.add("records_enqueued")

    def stop(self) -> None:
        """Atomically end admission and place the sentinel after accepted events."""
        with self.admission:
            if not self.closing:
                self.closing = True
                self.queue.put(None)
