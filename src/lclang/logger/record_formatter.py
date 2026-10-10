"""Configurable timestamp formatting without mutating shared records.

Defines ``RecordFormatter``.
"""

from __future__ import annotations

import copy
import logging
from datetime import UTC, datetime
from typing import Literal

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

# Unitless LogRecord extras shared with wrappers and the CLI result/audit adapter.
PREFIX_ATTRIBUTE = "lclang_prefix"
FILE_ONLY_ATTRIBUTE = "lclang_file_only"


@guard_constructor(LclValidationError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
class RecordFormatter(logging.Formatter):
    """Format a detached record with a first-line prefix and zoned timestamp."""

    def __init__(self, fmt: str, *, timezone: Literal["local", "utc"] = "local") -> None:
        """Attach the validated timestamp policy to the shared percent formatter.

        :param fmt: Percent-style logging format.
        :param timezone: Validated local or utc timestamp policy.
        :raises LclValidationError: If the logging format is invalid.
        """
        super().__init__(fmt)
        self.timezone = timezone

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Render the producer timestamp with its event-time timezone offset.

        :param record: Original event record.
        :param datefmt: Ignored stdlib customization; timestamps always use ISO format.
        :returns: Microsecond timestamp with a local numeric offset or UTC Z suffix.
        """
        timestamp = datetime.fromtimestamp(record.created, UTC)
        if self.timezone == "local":
            return timestamp.astimezone().isoformat(timespec="microseconds")
        return timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def format(self, record: logging.LogRecord) -> str:
        """Insert prefix while preserving the incoming message and arguments.

        :param record: Queue-owned record.
        :returns: Formatted message with optional traceback.
        """
        detached = copy.copy(record)
        prefix = getattr(record, PREFIX_ATTRIBUTE, "")
        detached.msg = (prefix + " " if prefix else "") + record.getMessage()
        detached.args = ()
        detached.exc_text = None
        return super().format(detached)
