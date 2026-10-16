"""Lightweight scope-independent wrappers using stdlib caller attribution.

Defines ``Logger``.
"""

from __future__ import annotations

import logging
from typing import Any

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.config_validation import boolean
from lclang.logger.record_formatter import COMPACT_ATTRIBUTE, PREFIX_ATTRIBUTE
from lclang.logger.runtime_registry import current_runtime


@guard_constructor(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
class Logger:
    """Bind only a stdlib source name, prefix, and caller offset."""

    def __init__(self, name: str | None, prefix: str, emit_level: int) -> None:
        """Retain wrapper settings without owning a runtime or handlers.

        :param name: Stdlib source name; None selects root.
        :param prefix: Text inserted once at formatting time.
        :param emit_level: Additional application wrapper frames to skip.
        """
        self.backend = logging.getLogger(name)
        self.prefix, self.emit_level = prefix, emit_level

    @property
    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def name(self) -> str:
        """Return the stdlib source name.

        :returns: Registered source name.
        """
        return self.backend.name

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def isEnabledFor(self, level: int) -> bool:
        """Check scope admission and the stdlib logger threshold.

        :param level: Candidate severity.
        :returns: Whether a producer should construct the event.
        """
        return not current_runtime().handler.closing and self.backend.isEnabledFor(level)

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def log(
        self, level: int, msg: object, *args: object, compact: bool = False, **kwargs: Any
    ) -> None:
        """Forward a record with prefix metadata and adjusted stacklevel.

        :param level: Numeric severity.
        :param msg: Stdlib message object or formatting template.
        :param args: Deferred message formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib extra, exception and caller options.
        :raises LclValidationError: If compact is not Boolean.
        """
        boolean(compact, "compact")
        runtime = current_runtime()
        with runtime.handler.admission:
            if runtime.handler.closing:
                return
            extra = dict(kwargs.pop("extra", None) or {})
            extra[PREFIX_ATTRIBUTE] = self.prefix
            extra[COMPACT_ATTRIBUTE] = compact
            stacklevel = kwargs.pop("stacklevel", 1) + self.emit_level + 2
            self.backend.log(level, msg, *args, extra=extra, stacklevel=stacklevel, **kwargs)

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def debug(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit DEBUG through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options.
        :raises LclValidationError: If compact is not Boolean.
        """
        self.log(
            logging.DEBUG,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def info(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit INFO through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options.
        :raises LclValidationError: If compact is not Boolean.
        """
        self.log(
            logging.INFO,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def warning(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit WARNING through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options.
        :raises LclValidationError: If compact is not Boolean.
        """
        self.log(
            logging.WARNING,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def error(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit ERROR through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options.
        :raises LclValidationError: If compact is not Boolean.
        """
        self.log(
            logging.ERROR,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def critical(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit CRITICAL through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options.
        :raises LclValidationError: If compact is not Boolean.
        """
        self.log(
            logging.CRITICAL,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def exception(self, msg: object, *args: object, compact: bool = False, **kwargs: Any) -> None:
        """Emit ERROR with the current exception unless explicitly overridden.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param compact: Whether to omit logger name and source location in default layouts.
        :param kwargs: Stdlib logging options including optional exc_info.
        :raises LclValidationError: If compact is not Boolean.
        """
        kwargs.setdefault("exc_info", True)
        self.log(
            logging.ERROR,
            msg,
            *args,
            compact=compact,
            stacklevel=kwargs.pop("stacklevel", 1) + 2,
            **kwargs,
        )
