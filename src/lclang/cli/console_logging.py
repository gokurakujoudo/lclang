"""Independent stdout and stderr logging for CLI applications."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

from lclang.cli.logging import LoggerHandle

# LogRecord attribute marking records intended only for the configured file sink.
FILE_ONLY_ATTRIBUTE = "lclang_file_only"


def attach_console_handlers(handle: LoggerHandle, verbose: bool) -> None:
    """Print non-error records to stdout and errors to stderr.

    :param handle: Configured invocation logger owner.
    :param verbose: Whether application DEBUG records are visible.
    :returns: ``None``.
    """
    level = logging.DEBUG if verbose else logging.INFO
    formatter = handle.handlers[0].formatter
    output: logging.StreamHandler[TextIO] = logging.StreamHandler(sys.stdout)
    output.setLevel(level)
    output.setFormatter(formatter)
    output.addFilter(terminal_record)
    errors: logging.StreamHandler[TextIO] = logging.StreamHandler(sys.stderr)
    errors.setLevel(logging.ERROR)
    errors.setFormatter(formatter)
    errors.addFilter(terminal_error_record)
    handle.logger.setLevel(min(handle.logger.level, level))
    handle.logger.addHandler(output)
    handle.logger.addHandler(errors)
    handle.handlers += (output, errors)


def terminal_record(record: logging.LogRecord) -> bool:
    """Select non-error records not already rendered as command results.

    :param record: Candidate application logging record.
    :returns: Whether the stdout handler should emit the record.
    """
    return record.levelno < logging.ERROR and not getattr(
        record,
        FILE_ONLY_ATTRIBUTE,
        False,
    )


def terminal_error_record(record: logging.LogRecord) -> bool:
    """Exclude error records already rendered as command results.

    :param record: Candidate application logging record.
    :returns: Whether the stderr handler should emit the record.
    """
    return not getattr(record, FILE_ONLY_ATTRIBUTE, False)
