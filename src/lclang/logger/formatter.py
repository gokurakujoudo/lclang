"""UTC formatting without mutating records shared with other handlers."""

from __future__ import annotations

import copy
import logging
from datetime import UTC, datetime

# Unitless LogRecord extras shared with wrappers and the CLI result/audit adapter.
PREFIX_ATTRIBUTE = "lclang_prefix"
FILE_ONLY_ATTRIBUTE = "lclang_file_only"


class RecordFormatter(logging.Formatter):
    """Format a detached record with a first-line prefix and UTC timestamp."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Render the producer timestamp in UTC at microsecond precision.

        :param record: Original event record.
        :param datefmt: Ignored stdlib customization; timestamps always use ISO UTC.
        :returns: ISO timestamp ending in Z.
        """
        return (
            datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

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
