"""Framework timestamps and default compact, verbose, lifecycle and event layouts.

Defines ``RecordFormatter``.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from lclang.error import LclLoggerError, LclValidationError, LoggerErrorCode
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.handler_config import DEFAULT_FORMAT, EVENT_FORMAT, VERBOSE_FORMAT
from lclang.logger.lcl_exception_formatter import LclExceptionFormatter

# Unitless LogRecord extras shared by wrappers and CLI failure reporting.
PREFIX_ATTRIBUTE = "lclang_prefix"
COMPACT_ATTRIBUTE = "lclang_compact"
FILE_ONLY_ATTRIBUTE = "lclang_file_only"
DIAGNOSTIC_ATTRIBUTE = "lclang_failure_diagnostic"


@guard_constructor(LclValidationError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
class RecordFormatter(LclExceptionFormatter):
    """Apply zoned timestamps and display-only verbose layouts to borrowed records."""

    def __init__(
        self,
        fmt: str,
        *,
        timezone: Literal["local", "utc"] = "local",
        traceback_style: Literal["compact", "full"] = "compact",
    ) -> None:
        """Prepare timestamp and exception policies without installing handlers.

        :param fmt: Explicit percent layout or the framework default layout.
        :param timezone: Validated local or utc timestamp policy.
        :param traceback_style: Compact language-frame filtering or full Python stacks.
        :raises LclValidationError: If format or traceback policy is invalid.
        """
        super().__init__(fmt, traceback_style=traceback_style)
        self.timezone = timezone
        self.verbose_formatter = (
            RecordFormatter(VERBOSE_FORMAT, timezone=timezone, traceback_style=traceback_style)
            if fmt == DEFAULT_FORMAT
            else None
        )
        self.event_formatter = (
            RecordFormatter(EVENT_FORMAT, timezone=timezone, traceback_style=traceback_style)
            if fmt == DEFAULT_FORMAT
            else None
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Render the producer timestamp with its event-time timezone offset.

        :param record: Original event record.
        :param datefmt: Ignored; framework timestamps always use ISO format.
        :returns: Microsecond timestamp with a local offset or UTC Z suffix.
        """
        timestamp = datetime.fromtimestamp(record.created, UTC)
        if self.timezone == "local":
            return timestamp.astimezone().isoformat(timespec="microseconds")
        return timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def format(self, record: logging.LogRecord) -> str:
        """Select marked default layouts without overriding application formats.

        :param record: Queue-owned producer record, never modified by formatting.
        :returns: Configured log text with protected exception trees when present.
        """
        if self.verbose_formatter is not None and (
            getattr(record, COMPACT_ATTRIBUTE, False)
            or getattr(record, "lclang_verbose", False)
            or getattr(record, "lclang_workflow_lifecycle", False)
        ):
            return self.verbose_formatter.format(record)
        if self.event_formatter is not None and hasattr(record, "lclang_event"):
            return self.event_formatter.format(record)
        return super().format(record)
