"""Single-threaded sink dispatch, timer scheduling, and error isolation."""

from __future__ import annotations

import logging
import sys
import time
from contextlib import suppress
from queue import Empty, SimpleQueue
from threading import Event

from lclang.logger.config import LoggerHandlerConfig
from lclang.logger.console import ConsoleSink
from lclang.logger.file import FileSink
from lclang.logger.formatter import RecordFormatter
from lclang.logger.metrics import Counters, SinkMetrics


class Dispatcher:
    """Run all output operations in one dedicated thread."""

    def __init__(
        self,
        config: LoggerHandlerConfig,
        queue: SimpleQueue[logging.LogRecord | None],
        counters: Counters,
    ) -> None:
        """Attach queue and configuration without performing output.

        :param config: Validated process configuration.
        :param queue: Process-local record queue; None is the shutdown sentinel.
        :param counters: Shared diagnostics.
        """
        self.config, self.queue, self.counters = config, queue, counters
        self.ready = Event()
        self.startup_error: BaseException | None = None
        self.sinks: list[ConsoleSink | FileSink] = []

    def report(self, sink: ConsoleSink | FileSink, error: BaseException) -> None:
        """Count an output failure without recursively using logging.

        :param sink: Failed output.
        :param error: Original writer exception.
        """
        self.counters.add("writer_errors", sink.key)
        self.counters.add("writer_errors")
        with suppress(Exception):
            if sys.__stderr__ is not None:
                sys.__stderr__.write(f"lclang.logger {sink.key}: {type(error).__name__}\n")

    def initialize(self) -> None:
        """Create all enabled sinks before producer admission begins."""
        formatter = RecordFormatter(self.config.format)
        console = self.config.resolved_console()
        if console.enabled:
            self.sinks.append(ConsoleSink(console, formatter))
        for name, config in self.config.resolved_files().items():
            if config.enabled:
                self.sinks.append(FileSink(name, config, formatter, self.counters))
        with self.counters.lock:
            for sink in self.sinks:
                self.counters.sinks.setdefault(sink.key, SinkMetrics())

    def fail(self, sink: ConsoleSink | FileSink, error: Exception) -> None:
        """Retire failed file streams and isolate secondary close errors.

        :param sink: Failed output.
        :param error: Primary output failure.
        """
        self.report(sink, error)
        if isinstance(sink, FileSink):
            try:
                sink.close()
            except Exception as close_error:
                self.report(sink, close_error)

    def dispatch(self, record: logging.LogRecord) -> None:
        """Write independently to every matching sink.

        :param record: Queue-owned event.
        """
        written = False
        for sink in self.sinks:
            try:
                if sink.accepts(record):
                    self.counters.add("records_enqueued", sink.key)
                    sink.write(record)
                    self.counters.add("records_written", sink.key)
                    written = True
            except Exception as error:
                self.fail(sink, error)
        if written:
            self.counters.add("records_written")

    def timers(self) -> float:
        """Process timers between records to avoid busy-queue starvation.

        :returns: Seconds until the next timer, capped to observe wall-clock changes.
        """
        monotonic, wall = time.monotonic(), time.time()
        timeout = 1.0
        for sink in self.sinks:
            if isinstance(sink, FileSink):
                try:
                    sink.process_timers(monotonic, wall)
                except Exception as error:
                    self.fail(sink, error)
                timeout = min(timeout, sink.timeout(monotonic, wall))
        return timeout

    def run(self) -> None:
        """Initialize, drain through the sentinel, and retire every owned sink."""
        try:
            try:
                self.initialize()
            except BaseException as error:
                self.startup_error = error
                return
            finally:
                self.ready.set()
            while True:
                timeout = self.timers()
                try:
                    record = self.queue.get(timeout=timeout)
                except Empty:
                    continue
                if record is None:
                    break
                self.dispatch(record)
        finally:
            for sink in self.sinks:
                try:
                    sink.close()
                except Exception as error:
                    self.report(sink, error)
