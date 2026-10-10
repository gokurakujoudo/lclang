"""Immutable public logger declarations preserving explicit field presence.

Defines ``merge_fields``, ``LoggerHandlerConfig``, ``handler_config``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from lclang.error import LclLoggerError, LoggerErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger.config_validation import boolean, fields, freeze, level, mapping, names
from lclang.logger.sink_config import ConsoleConfig, FileConfig, console_config, file_config

# Unitless format and takeover names follow the logger reference and CLI diagnostic layout.
DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | pid=%(process)d thread=%(threadName)s | "
    "%(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"
)
DEFAULT_TAKEOVER = ("uvicorn", "uvicorn.error", "uvicorn.access")
CONFIG_FIELDS = {
    "level",
    "format",
    "console",
    "file",
    "takeover_loggers",
    "capture_warnings",
    "timezone",
}


@guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
def merge_fields(
    defaults: Mapping[str, object], explicit: Mapping[str, object]
) -> dict[str, object]:
    """Fill absent leaf fields, including rotation fields, from a template.

    :param defaults: Lower-priority declaration.
    :param explicit: Higher-priority declaration preserving absent fields.
    :returns: Detached merged fields.
    """
    result = dict(defaults)
    for key, value in explicit.items():
        result[key] = (
            merge_fields(mapping(result.get(key, {}), key), mapping(value, key))
            if key == "rotation"
            else value
        )
    return result


@guard_constructor(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class LoggerHandlerConfig:
    """Declare process-wide output without losing template inheritance.

    :param level: Global minimum severity; NOTSET admits all normal levels.
    :param format: Shared percent-style format; timestamps and prefix are formatter-owned.
    :param console: Borrowed console declaration, enabled on stderr by default.
    :param file: Named file declarations; default supplies absent fields only.
    :param takeover_loggers: Logger names whose handlers and levels are temporarily replaced.
    :param capture_warnings: Whether to redirect warnings during the scope.
    :param timezone: Log timestamp policy, local with numeric offset or utc with Z.
    """

    level: int | str = logging.NOTSET
    format: str = DEFAULT_FORMAT
    console: Mapping[str, object] = field(default_factory=dict[str, object])
    file: Mapping[str, object] = field(default_factory=dict[str, object])
    takeover_loggers: tuple[str, ...] = DEFAULT_TAKEOVER
    capture_warnings: bool = False
    timezone: Literal["local", "utc"] = "local"

    @guard_failure(LclValidationError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Freeze declaration containers and validate all effective sinks.

        :raises LclValidationError: If a format or declaration has an invalid type.
        :raises LclValidationError: If sink names or policies are invalid.
        """
        if not isinstance(self.timezone, str):
            raise LclValidationError(
                "logger.timezone: expected text",
                code=LoggerErrorCode.E11_LOGGER_TIMEZONE_EXPECTED_TEXT,
            )
        if self.timezone not in ("local", "utc"):
            raise LclValidationError(
                "logger.timezone: expected local or utc",
                code=LoggerErrorCode.E11_LOGGER_TIMEZONE_EXPECTED_LOCAL_OR_UTC,
            )
        if not isinstance(self.format, str):
            raise LclValidationError(
                "logger.format: expected text", code=LoggerErrorCode.E11_LOGGER_FORMAT_EXPECTED_TEXT
            )
        try:
            logging.Formatter(self.format)
        except (ValueError, LclValidationError) as error:
            raise LclValidationError(
                f"logger.format: {error}", code=LoggerErrorCode.E11_LOGGER_FORMAT
            ) from error
        object.__setattr__(self, "level", level(self.level, "logger.level"))
        object.__setattr__(self, "console", freeze(mapping(self.console, "logger.console")))
        object.__setattr__(self, "file", freeze(mapping(self.file, "logger.file")))
        object.__setattr__(
            self, "takeover_loggers", names(self.takeover_loggers, "logger.takeover_loggers")
        )
        boolean(self.capture_warnings, "logger.capture_warnings")
        self.resolved_console()
        self.resolved_files()

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def resolved_console(self) -> ConsoleConfig:
        """Resolve the console without mutating the declaration.

        :returns: Complete console configuration.
        """
        return console_config(self.console)

    @guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
    def resolved_files(self) -> dict[str, FileConfig]:
        """Resolve file templates after all input sources have been layered.

        :returns: Concrete sinks, excluding the default template.
        :raises LclValidationError: If a sink identifier is invalid.
        """
        defaults = mapping(self.file.get("default", {}), "logger.file.default")
        file_config("default", defaults, template=True)
        result: dict[str, FileConfig] = {}
        for name, value in self.file.items():
            if not name.isidentifier():
                raise LclValidationError(
                    f"logger.file.{name}: expected sink identifier",
                    code=LoggerErrorCode.E11_LOGGER_FILE_SINK_IDENTIFIER_TYPE,
                )
            if name != "default":
                result[name] = file_config(
                    name, merge_fields(defaults, mapping(value, f"logger.file.{name}"))
                )
        return result


@guard_failure(LclLoggerError, LoggerErrorCode.E11_LOGGER_CONFIGURATION_NATIVE_FAILURE)
def handler_config(value: LoggerHandlerConfig | Mapping[str, object]) -> LoggerHandlerConfig:
    """Accept either a validated object or the public mapping shape.

    :param value: Handler configuration.
    :returns: Immutable validated configuration.
    """
    if isinstance(value, LoggerHandlerConfig):
        return value
    data = fields(value, CONFIG_FIELDS, "logger")
    return LoggerHandlerConfig(**data)  # type: ignore[arg-type]
