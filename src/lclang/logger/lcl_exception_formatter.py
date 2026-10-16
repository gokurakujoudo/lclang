"""Opt-in standard logging formatter for protected LCL diagnostic trees.

Defines ``LclExceptionFormatter``.
"""

import copy
import logging
from collections.abc import Mapping
from types import TracebackType
from typing import Literal

from lclang.error import LclLoggerError, LclValidationError, LoggerErrorCode
from lclang.error.exception_report import render_exception_report
from lclang.error.failure_traceback import render_failure_traceback
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.traceback_policy import validate_traceback_style

# Unitless display labels follow the logger reference; original severity names
# remain available to filters, configuration and other handlers.
DISPLAY_LEVEL_NAMES = {"WARNING": "WARN", "CRITICAL": "CRIT", "NOTSET": "UNSET"}


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
        return render_exception_report(error, ei[2], traceback_style=self.traceback_style)

    @guard_failure(LclLoggerError, LoggerErrorCode.E41_LOG_FORMATTING_NATIVE_FAILURE)
    def format(self, record: logging.LogRecord) -> str:
        """Render a detached record with compact display labels and caller metadata.

        :param record: Original producer record, borrowed without modification.
        :returns: Message plus a single diagnostic and optional traceback tree.
        """
        detached = copy.copy(record)
        detached.levelname = (
            "TRACE"
            if getattr(record, "lclang_verbose", False)
            else DISPLAY_LEVEL_NAMES.get(record.levelname, record.levelname)
        )
        module_name = getattr(record, "lclang_module_name", None)
        detached.lclang_source_file = f"{module_name}.py" if module_name else record.filename
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
