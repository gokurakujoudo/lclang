"""Opt-in standard logging formatter for protected LCL diagnostic trees.

Defines ``LclExceptionFormatter``.
"""

import copy
import logging
from collections.abc import Mapping
from types import TracebackType
from typing import Literal

from lclang.error import LclError, LclLoggerError, LclValidationError, LoggerErrorCode
from lclang.error.diagnostic_rendering import render_error, render_failure
from lclang.error.failure_traceback import render_failure_traceback
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.traceback_policy import validate_traceback_style


@guard_constructor(LclValidationError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
class LclExceptionFormatter(logging.Formatter):
    """Format borrowed records without modifying logging levels or exceptions."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        defaults: Mapping[str, object] | None = None,
        traceback_style: Literal["compact", "full"] = "compact",
    ) -> None:
        """Accept standard formatter arguments and an explicit traceback policy.

        :param fmt: Standard logging layout, or the standard message-only default.
        :param datefmt: Standard timestamp format used by external handlers.
        :param style: Percent, brace or dollar logging layout syntax.
        :param validate: Whether the standard library validates layout syntax.
        :param defaults: Static standard-library record field defaults.
        :param traceback_style: Compact language-frame filtering or all Python frames.
        :raises LclValidationError: If layout or traceback policy is invalid.
        """
        self.traceback_style: Literal["compact", "full"] = validate_traceback_style(traceback_style)
        super().__init__(
            fmt, datefmt, style, validate, defaults=None if defaults is None else dict(defaults)
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def formatException(
        self,
        ei: (
            tuple[type[BaseException], BaseException, TracebackType | None]
            | tuple[None, None, None]
        ),
    ) -> str:
        """Produce one full diagnostic followed by concise Python exception evidence.

        :param ei: Standard exception type, object and traceback tuple.
        :returns: Uniform diagnostic and Python exception trees.
        """
        error = ei[1]
        if error is None:
            return ""
        diagnostic = (
            render_error(error)
            if isinstance(error, LclError)
            else render_failure(error, action="handling failure")
        )
        trace = render_failure_traceback(
            error, ei[2], style=self.traceback_style, require_frames=True
        )
        return diagnostic + ("\nPython traceback:\n" + trace if trace else "")

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def format(self, record: logging.LogRecord) -> str:
        """Render a detached record with display-only verbose labels and prefixes.

        :param record: Original producer record, borrowed without modification.
        :returns: Message plus a single diagnostic and optional traceback tree.
        """
        detached = copy.copy(record)
        if getattr(record, "lclang_verbose", False):
            detached.levelname = "VERBOSE"
        prefix = getattr(record, "lclang_prefix", "")
        detached.msg = (prefix + " " if prefix else "") + record.getMessage()
        detached.args = ()
        detached.exc_text = None
        if getattr(record, "lclang_failure_diagnostic", False) and record.exc_info is not None:
            detached.exc_info = None
            formatted = super().format(detached)
            error = record.exc_info[1]
            if error is not None:
                trace = render_failure_traceback(
                    error, record.exc_info[2], style=self.traceback_style, require_frames=True
                )
                if trace:
                    formatted += "\nPython traceback:\n" + trace
            return formatted
        return super().format(detached)
