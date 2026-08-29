"""Isolated standard-library logging for CLI invocations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from logging.handlers import MemoryHandler
from pathlib import Path
from typing import TextIO, cast

from lclang.cli.audit import (
    AUDIT_RECORD_ATTRIBUTE,
    emit_execution_start,
    normalized_argv,
    redacted_overrides,
)
from lclang.cli.models import CliParams, LogConfig
from lclang.runtime import Frame

# Compatibility exports retained for existing CLI logging callers.
__all__ = [
    "AUDIT_RECORD_ATTRIBUTE",
    "normalized_argv",
    "redacted_overrides",
]


@dataclass(frozen=True, slots=True)
class InvocationLevelFilter:
    """Apply the configured level only to one invocation logger.

    :param logger_name: Application logger governed by the file threshold.
    :param level: Minimum application record level written to the file.
    """

    logger_name: str
    level: int

    def filter(self, record: logging.LogRecord) -> bool:
        """Keep audit and verbose records while filtering application records.

        :param record: Candidate file logging record.
        :returns: Whether the configured file handler should emit it.
        """
        return (
            getattr(record, AUDIT_RECORD_ATTRIBUTE, False)
            or record.name != self.logger_name
            or record.levelno >= self.level
        )


@dataclass(slots=True)
class LoggerHandle:
    """Own one isolated command logger and its handlers.

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


@dataclass(slots=True)
class VerboseLoggerHandle:
    """Own one stderr trace logger and its temporary replay buffer.

    :param logger: Non-propagating DEBUG logger activated task-locally.
    :param stream_handler: Immediate deterministic stderr output.
    :param buffer_handler: Early records awaiting effective file configuration.
    :param borrowed_handler: Invocation handler receiving replayed and future records.
    :param closed: Whether owned handlers have already been detached.
    """

    logger: logging.Logger
    stream_handler: logging.StreamHandler[TextIO]
    buffer_handler: MemoryHandler | None
    borrowed_handler: logging.Handler | None = None
    closed: bool = False

    def attach(self, handler: logging.Handler) -> None:
        """Replay early records and forward future traces to an invocation handler.

        :param handler: Configured handler borrowed from a :class:`LoggerHandle`.
        :returns: ``None``.
        """
        if self.closed or self.borrowed_handler is not None:
            return
        buffer = cast(MemoryHandler, self.buffer_handler)
        for record in tuple(buffer.buffer):
            handler.handle(record)
        buffer.buffer.clear()
        self.logger.removeHandler(buffer)
        buffer.close()
        self.buffer_handler = None
        self.borrowed_handler = handler
        self.logger.addHandler(handler)

    def close(self) -> None:
        """Detach borrowed state and close only handlers owned by this trace logger.

        :returns: ``None``.
        """
        if self.closed:
            return
        self.closed = True
        if self.borrowed_handler is not None:
            self.logger.removeHandler(self.borrowed_handler)
            self.borrowed_handler = None
        if self.buffer_handler is not None:
            self.logger.removeHandler(self.buffer_handler)
            self.buffer_handler.close()
            self.buffer_handler = None
        self.logger.removeHandler(self.stream_handler)
        self.stream_handler.close()


def create_verbose_logger(identity: str) -> VerboseLoggerHandle:
    """Create one non-propagating stderr logger with an early-record buffer.

    :param identity: Stable per-call logger suffix.
    :returns: Owned verbose logger ready for task-local activation.
    """
    logger = logging.Logger(f"lclang.verbose.{identity}", logging.DEBUG)
    logger.propagate = False
    stream: logging.StreamHandler[TextIO] = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    # The configured CLI handler does not exist until Frame log values resolve.
    buffer = MemoryHandler(capacity=1_000_000, flushLevel=logging.CRITICAL + 1)
    logger.addHandler(stream)
    logger.addHandler(buffer)
    return VerboseLoggerHandle(logger, stream, buffer)


async def resolve_log_config(frame: Frame) -> LogConfig:
    """Evaluate effective logger fields through the final Frame.

    :param frame: Top invocation Frame.
    :returns: Validated effective log configuration.
    :raises Exception: If evaluation or validation fails.
    """
    return LogConfig(
        log_dir=cast(str | None, await frame.get("logger.log_dir")),
        log_file_name=cast(str, await frame.get("logger.log_file_name")),
        log_level=cast(str | int, await frame.get("logger.log_level")),
        log_format=cast(str, await frame.get("logger.log_format")),
    )


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


async def create_logger(frame: Frame, identity: str) -> LoggerHandle:
    """Create one non-propagating logger from effective Frame values.

    :param frame: Top invocation Frame.
    :param identity: Stable per-call logger suffix.
    :returns: Owned configured logger handle.
    :raises OSError: If an enabled directory or file cannot be created.
    :raises Exception: If effective values fail evaluation or validation.
    """
    config = await resolve_log_config(frame)
    level = numeric_log_level(config.log_level)
    logger = logging.Logger(f"lclang.cli.{identity}", level)
    logger.propagate = False
    handler = await asyncio.to_thread(build_handler, config)
    handler.addFilter(InvocationLevelFilter(logger.name, level))
    logger.addHandler(handler)
    path = Path(handler.baseFilename) if isinstance(handler, logging.FileHandler) else None
    return LoggerHandle(logger, (handler,), path)


def log_execution_start(
    handle: LoggerHandle,
    params: CliParams,
    frame: Frame,
    names: tuple[str, ...] = (),
) -> None:
    """Write the fixed audit preamble before command or verbose records.

    :param handle: Configured invocation logger owner.
    :param params: Parsed invocation values.
    :param frame: Effective invocation Frame carrying sticky mask metadata.
    :param names: Command and file configuration names to render.
    :returns: ``None``.
    """
    original_level = handle.logger.level
    handle.logger.setLevel(min(original_level, logging.INFO))
    try:
        emit_execution_start(handle.logger, handle.log_path, params, frame, names)
    finally:
        handle.logger.setLevel(original_level)
