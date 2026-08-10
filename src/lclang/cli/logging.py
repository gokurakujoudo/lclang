"""Isolated standard-library logging for CLI invocations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lclang.cli.models import LogConfig
from lclang.runtime import Frame


@dataclass(slots=True)
class LoggerHandle:
    """Own one isolated command logger and its handlers.

    :param logger: Handler-visible standard-library logger.
    :param handlers: Handlers to detach and close.
    :param closed: Whether cleanup has already occurred.
    """

    logger: logging.Logger
    handlers: tuple[logging.Handler, ...]
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


async def resolve_log_config(frame: Frame) -> LogConfig:
    """Evaluate effective logger fields through the final Frame.

    :param frame: Top invocation Frame.
    :returns: Validated effective log configuration.
    :raises Exception: If evaluation or validation fails.
    """
    return LogConfig(
        log_dir=cast(str | None, await frame.get("log_dir")),
        log_file_name=cast(str, await frame.get("log_file_name")),
        log_level=cast(str | int, await frame.get("log_level")),
        log_format=cast(str, await frame.get("log_format")),
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
    logger = logging.Logger(f"lclang.cli.{identity}", numeric_log_level(config.log_level))
    logger.propagate = False
    handler = await asyncio.to_thread(build_handler, config)
    logger.addHandler(handler)
    return LoggerHandle(logger, (handler,))
