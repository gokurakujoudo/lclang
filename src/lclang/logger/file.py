"""Writer-owned binary file sink with permanent segment transitions."""

from __future__ import annotations

import logging
import time
from typing import BinaryIO

from lclang.logger.formatter import RecordFormatter
from lclang.logger.metrics import Counters
from lclang.logger.rotation import RotationTimer
from lclang.logger.segments import create_segment, path_line
from lclang.logger.sink_config import FileConfig


class FileSink:
    """Own one file stream and its independent size, flush, and time state."""

    def __init__(
        self, name: str, config: FileConfig, formatter: RecordFormatter, counters: Counters
    ) -> None:
        """Initialize an enabled file in the dispatcher thread.

        :param name: Configuration sink identifier.
        :param config: Resolved enabled file policy.
        :param formatter: Shared record formatter.
        :param counters: Runtime diagnostics.
        """
        self.key = f"file.{name}"
        self.config, self.formatter, self.counters = config, formatter, counters
        self.stream: BinaryIO | None = None
        self.current_size = 0
        self.records = 0
        self.timer = RotationTimer(config.rotation, time.monotonic(), time.time())
        self.next_flush = time.monotonic() + config.flush_interval
        self.open_segment()

    def open_segment(self) -> None:
        """Create a new permanent segment without reopening old output."""
        self.path, self.stream, self.current_size = create_segment(self.config)
        self.records = 0
        self.counters.set_path(self.key, self.path)

    def accepts(self, record: logging.LogRecord) -> bool:
        """Filter by minimum level and exact/dotted ancestor names.

        :param record: Candidate queue record.
        :returns: Whether the file should receive the record.
        """
        return record.levelno >= self.config.level and (
            not self.config.logger_names
            or any(
                record.name == name or record.name.startswith(name + ".")
                for name in self.config.logger_names
            )
        )

    def rollover(self) -> None:
        """Create the successor before sealing the previous segment.

        :raises OSError: If segment creation, footer writing, or flushing fails.
        """
        path, stream, size = create_segment(self.config)
        previous = self.stream
        self.path, self.stream, self.current_size = path, stream, size
        self.records = 0
        self.counters.set_path(self.key, path)
        if previous is not None:
            try:
                previous.write(path_line("continued in", path, self.config.encoding))
                previous.flush()
            finally:
                previous.close()
        self.counters.add("rollover_count", self.key)
        self.counters.add("rollover_count")

    def write(self, record: logging.LogRecord) -> None:
        """Write an intact encoded record, rotating before size overflow.

        :param record: Selected queue record.
        """
        data = (self.formatter.format(record) + "\n").encode(
            self.config.encoding, "backslashreplace"
        )
        if self.stream is None:
            self.open_segment()
        rotation = self.config.rotation
        if (
            self.records
            and rotation.mode in ("size", "size_or_time")
            and self.current_size + len(data) > rotation.max_bytes
        ):
            self.rollover()
        assert self.stream is not None
        self.stream.write(data)
        self.current_size += len(data)
        self.records += 1

    def process_timers(self, monotonic: float, wall: float) -> None:
        """Process scheduled rollover and periodic flushing even when idle.

        :param monotonic: Current monotonic seconds.
        :param wall: Current Unix seconds.
        """
        if self.timer.remaining(monotonic, wall) == 0:
            self.timer.advance(monotonic, wall)
            self.rollover()
        if monotonic >= self.next_flush:
            self.next_flush = monotonic + self.config.flush_interval
            if self.stream is not None:
                self.stream.flush()

    def timeout(self, monotonic: float, wall: float) -> float:
        """Compute a nonnegative wait before the next required operation.

        :param monotonic: Current monotonic seconds.
        :param wall: Current Unix seconds.
        :returns: Delay in seconds, capped at one second to observe wall-clock changes.
        """
        return max(
            0.0, min(1.0, self.next_flush - monotonic, self.timer.remaining(monotonic, wall))
        )

    def close(self) -> None:
        """Detach first, then flush and close without allowing future appends."""
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.flush()
            finally:
                stream.close()
