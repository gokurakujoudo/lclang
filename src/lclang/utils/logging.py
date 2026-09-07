"""Standalone configured standard-library logging utilities."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

# Default pipe-delimited format retaining diagnostic fields.
# Unitless format and field names below follow Python logging percent-style syntax. The project
# format retains time, severity, source and message; mandatory fields preserve useful
# diagnostics in caller-supplied layouts.
DEFAULT_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | "
    "%(funcName)s | %(message)s"
)
# Required percent fields that custom formats must retain.
REQUIRED_LOG_FIELDS = (
    "asctime",
    "levelname",
    "filename",
    "lineno",
    "funcName",
    "message",
)


@dataclass(frozen=True, slots=True)
class LogConfig:
    """Define effective file logging configuration.

    :param log_dir: Directory for the log file, or ``None`` to disable output.
    :param log_file_name: Leaf log filename.
    :param log_level: Standard integer level or case-insensitive level name.
    :param log_format: Percent-style logging format with required fields.
    """

    log_dir: str | None = None
    log_file_name: str = "lclang.log"
    log_level: str | int = "INFO"
    log_format: str = DEFAULT_LOG_FORMAT

    def __post_init__(self) -> None:
        """Validate logging values without touching the filesystem.

        :returns: ``None``.
        :raises TypeError: If a field has an unsupported type.
        :raises ValueError: If a path, level, or format is invalid.
        """
        if self.log_dir is not None and not isinstance(self.log_dir, str):
            raise TypeError("log directory must be text or None")
        if self.log_dir == "":
            raise ValueError("log directory cannot be empty")
        if not isinstance(self.log_file_name, str):
            raise TypeError("log filename must be text")
        if not self.log_file_name or Path(self.log_file_name).name != self.log_file_name:
            raise ValueError("log filename must be a non-empty leaf name")
        if isinstance(self.log_level, str):
            if self.log_level.upper() not in logging.getLevelNamesMapping():
                raise ValueError("unknown log level")
        elif not isinstance(self.log_level, int):
            raise TypeError("log level must be text or integer")
        if not isinstance(self.log_format, str):
            raise TypeError("log format must be text")
        if any(f"%({name})" not in self.log_format for name in REQUIRED_LOG_FIELDS):
            raise ValueError("log format must contain every required diagnostic field")


@dataclass(slots=True)
class LoggerHandle:
    """Own one isolated logger and its handlers.

    :param logger: Handler-visible standard-library logger.
    :param handlers: Handlers to detach and close.
    :param log_path: Absolute enabled file path, or ``None`` for null logging.
    :param closed: Whether cleanup has already occurred.
    """

    logger: logging.Logger
    handlers: tuple[logging.Handler, ...]
    log_path: Path | None = None
    closed: bool = False

    def close(self) -> None:
        """Detach and close every owned handler once.

        :returns: ``None``.
        """
        if self.closed:
            return
        self.closed = True
        for handler in self.handlers:
            self.logger.removeHandler(handler)
            handler.close()


def numeric_log_level(value: str | int) -> int:
    """Convert a validated level value into its numeric representation.

    :param value: Standard level name or integer.
    :returns: Numeric logging level.
    """
    if isinstance(value, int):
        return value
    return logging.getLevelNamesMapping()[value.upper()]


def build_handler(config: LogConfig) -> logging.Handler:
    """Create one configured handler using blocking filesystem APIs.

    :param config: Validated effective log configuration.
    :returns: New null or UTF-8 file handler.
    :raises OSError: If an enabled directory or file cannot be created.
    """
    if config.log_dir is None:
        handler: logging.Handler = logging.NullHandler()
    else:
        directory = Path(config.log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(directory / config.log_file_name, encoding="utf-8")
    handler.setFormatter(logging.Formatter(config.log_format))
    return handler


async def create_logger(config: LogConfig, name: str) -> LoggerHandle:
    """Create one non-propagating configured logger.

    :param config: Validated standalone logging configuration.
    :param name: Non-empty exact logger name.
    :returns: Owned configured logger handle.
    :raises TypeError: If *config* or *name* has the wrong type.
    :raises ValueError: If *name* is empty.
    :raises OSError: If an enabled directory or file cannot be created.
    """
    if not isinstance(config, LogConfig):
        raise TypeError("logger config must be LogConfig")
    if not isinstance(name, str):
        raise TypeError("logger name must be text")
    if not name:
        raise ValueError("logger name cannot be empty")
    level = numeric_log_level(config.log_level)
    logger = logging.Logger(name, level)
    logger.propagate = False
    handler = await asyncio.to_thread(build_handler, config)
    logger.addHandler(handler)
    path = Path(handler.baseFilename) if isinstance(handler, logging.FileHandler) else None
    return LoggerHandle(logger, (handler,), path)
