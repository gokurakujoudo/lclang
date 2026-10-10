"""Thread-safe counters and detached diagnostics.

Defines ``SinkMetrics``, ``RuntimeMetrics``, ``Counters``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure


@guard_constructor(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class SinkMetrics:
    """Snapshot one sink's output state.

    :param records_enqueued: Records selected for dispatch to this sink.
    :param records_written: Successful record writes, excluding metadata.
    :param writer_errors: Failed writer operations.
    :param rollover_count: Completed segment switches.
    :param path: Current or last file path; None for console.
    """

    records_enqueued: int = 0
    records_written: int = 0
    writer_errors: int = 0
    rollover_count: int = 0
    path: Path | None = None


@guard_constructor(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    """Snapshot aggregate counters and named sink counters.

    :param records_enqueued: Records admitted before the sentinel.
    :param records_written: Records written successfully to at least one sink.
    :param writer_errors: Failed writer operations across sinks.
    :param rollover_count: Completed segment switches across files.
    :param sinks: Immutable sink snapshots keyed by console or file.name.
    """

    records_enqueued: int
    records_written: int
    writer_errors: int
    rollover_count: int
    sinks: Mapping[str, SinkMetrics]


@guard_constructor(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
class Counters:
    """Serialize diagnostic updates separately from producer admission."""

    def __init__(self) -> None:
        """Initialize unitless event counters from zero."""
        self.lock = RLock()
        self.totals: dict[str, int] = dict.fromkeys(
            ("records_enqueued", "records_written", "writer_errors", "rollover_count"),
            0,
        )
        self.sinks: dict[str, SinkMetrics] = {}

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def add(self, event: str, sink: str | None = None) -> None:
        """Increment an aggregate or sink counter.

        :param event: Counter field name.
        :param sink: Sink key, or None to update the aggregate.
        """
        from dataclasses import replace

        with self.lock:
            if sink is None:
                self.totals[event] += 1
            else:
                previous = self.sinks.get(sink, SinkMetrics())
                self.sinks[sink] = replace(previous, **{event: getattr(previous, event) + 1})

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def set_path(self, sink: str, path: Path) -> None:
        """Publish a newly created output path.

        :param sink: File sink key.
        :param path: Absolute segment filename.
        """
        from dataclasses import replace

        with self.lock:
            self.sinks[sink] = replace(self.sinks.get(sink, SinkMetrics()), path=path)

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def snapshot(self) -> RuntimeMetrics:
        """Read mutually consistent immutable counters.

        :returns: Detached runtime metrics.
        """
        with self.lock:
            return RuntimeMetrics(**self.totals, sinks=MappingProxyType(dict(self.sinks)))
