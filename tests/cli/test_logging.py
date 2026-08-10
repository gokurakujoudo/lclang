"""Behavioural tests for isolated CLI logger construction."""

import asyncio
import logging
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from pylcl.cli import CliConfig, CliContext, CliParams, CliResult, CliResultStatus, LogConfig, cli
from pylcl.cli.binding import build_binding
from pylcl.cli.logging import build_handler, create_logger, numeric_log_level, resolve_log_config


@cli.command()
async def logger_command(context: CliContext) -> CliResult:
    """Return a reusable logging result.

    :param context: Current invocation.
    :returns: Successful result.
    """
    return CliResult(CliResultStatus.SUCCESS, "")


def test_disabled_and_enabled_loggers_are_isolated_and_close() -> None:
    """Null logging creates nothing while file logging writes beneath temp roots."""
    params = CliParams("python", ("logger",), date.today(), False, None, {})
    binding = asyncio.run(build_binding(logger_command, params, CliConfig()))
    assert asyncio.run(resolve_log_config(binding.frame)).log_dir is None
    handle = asyncio.run(create_logger(binding.frame, "disabled"))
    assert isinstance(handle.handlers[0], logging.NullHandler)
    handle.close()
    handle.close()
    asyncio.run(binding.stack.close())

    with TemporaryDirectory() as directory:
        config = LogConfig(log_dir=directory)
        handler = build_handler(config)
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "value=%s", (2,), None)
        handler.emit(record)
        handler.close()
        assert "value=2" in (Path(directory) / "pylcl.log").read_text(encoding="utf-8")


def test_numeric_log_levels_accept_names_and_integers() -> None:
    """Validated standard logging levels map to numeric values."""
    assert numeric_log_level("info") == logging.INFO
    assert numeric_log_level(logging.ERROR) == logging.ERROR
