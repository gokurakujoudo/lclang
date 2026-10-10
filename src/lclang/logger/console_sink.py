"""Borrowed console output owned exclusively by the writer thread.

Defines ``ConsoleSink``.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO, cast

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.record_formatter import FILE_ONLY_ATTRIBUTE, RecordFormatter
from lclang.logger.sink_config import ConsoleConfig


@guard_constructor(LclValidationError, LoggerErrorCode.E34_CONSOLE_OUTPUT_NATIVE_FAILURE)
class ConsoleSink:
    """Write selected records to a borrowed text stream."""

    def __init__(self, config: ConsoleConfig, formatter: RecordFormatter) -> None:
        """Resolve a stream at scope entry rather than import time.

        :param config: Enabled console policy.
        :param formatter: Shared immutable formatting policy.
        """
        self.config = config
        self.formatter = formatter
        self.stream = cast(
            TextIO, getattr(sys, config.stream) if isinstance(config.stream, str) else config.stream
        )
        self.key = "console"

    @guard_failure(LclLoggerError, LoggerErrorCode.E34_CONSOLE_OUTPUT_NATIVE_FAILURE)
    def accepts(self, record: logging.LogRecord) -> bool:
        """Apply the console threshold and CLI result suppression.

        :param record: Candidate queue record.
        :returns: Whether to write the record.
        """
        return record.levelno >= self.config.level and not getattr(
            record, FILE_ONLY_ATTRIBUTE, False
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E34_CONSOLE_OUTPUT_NATIVE_FAILURE)
    def write(self, record: logging.LogRecord) -> None:
        """Format and flush one console record in the writer thread.

        :param record: Selected queue record.
        """
        self.stream.write(self.formatter.format(record) + "\n")
        self.stream.flush()

    @guard_failure(LclLoggerError, LoggerErrorCode.E34_CONSOLE_OUTPUT_NATIVE_FAILURE)
    def close(self) -> None:
        """Flush without closing a caller-owned stream."""
        self.stream.flush()
