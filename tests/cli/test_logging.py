"""Behavioural tests for isolated CLI logger construction."""

import asyncio
import logging
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import lclang
from lclang.cli import CliConfig, CliContext, CliParams, CliResult, CliResultStatus, LogConfig, cli
from lclang.cli.binding import build_binding
from lclang.cli.logging import (
    build_handler,
    create_logger,
    create_verbose_logger,
    numeric_log_level,
    resolve_log_config,
)
from lclang.diagnostics import internal_trace, internal_verbose_scope


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
        assert "value=2" in (Path(directory) / "lclang.log").read_text(encoding="utf-8")


def test_numeric_log_levels_accept_names_and_integers() -> None:
    """Validated standard logging levels map to numeric values."""
    assert numeric_log_level("info") == logging.INFO
    assert numeric_log_level(logging.ERROR) == logging.ERROR


def test_verbose_logger_replays_and_closes_every_lifecycle_shape() -> None:
    """Replay attachment, duplicate calls, and unattached cleanup are idempotent."""
    first = logging.NullHandler()
    second = logging.NullHandler()
    handle = create_verbose_logger("lifecycle")
    with internal_verbose_scope(handle.logger):
        internal_trace("test", "buffered")
    assert handle.buffer_handler is not None
    assert len(handle.buffer_handler.buffer) == 1
    handle.attach(first)
    handle.attach(second)
    assert handle.borrowed_handler is first
    handle.close()
    handle.close()
    handle.attach(second)
    assert handle.logger.handlers == []

    unattached = create_verbose_logger("unattached")
    unattached.close()
    assert unattached.logger.handlers == []


def test_multiple_invocation_loggers_do_not_mutate_root_or_leak_handlers() -> None:
    """Composite invocations remain isolated and reveal only explicit records."""
    root = logging.getLogger()
    root_handlers = tuple(root.handlers)
    with TemporaryDirectory() as directory:
        module = lclang.define_module("logging-audit", {})
        frame = lclang.define_frame(
            module,
            preset={
                "log_dir": directory,
                "log_file_name": "audit.log",
                "log_level": "INFO",
                "log_format": (
                    "%(asctime)s %(filename)s:%(lineno)d %(funcName)s "
                    "%(message)s args=%(args)r"
                ),
            },
        )

        async def exercise() -> None:
            """Create, use, and close two independent logger owners."""
            first = await create_logger(frame, "first")
            second = await create_logger(frame, "second")
            try:
                assert first.logger is not second.logger
                assert first.handlers[0] is not second.handlers[0]
                assert first.logger.propagate is second.logger.propagate is False
                first.logger.info("explicit-first")
                second.logger.info("explicit-second")
            finally:
                first.close()
                second.close()
                await frame.close()
            assert first.logger.handlers == []
            assert second.logger.handlers == []

        asyncio.run(exercise())
        contents = (Path(directory) / "audit.log").read_text(encoding="utf-8")
        assert "explicit-first" in contents
        assert "explicit-second" in contents
        assert "logging-audit" not in contents
    assert tuple(root.handlers) == root_handlers
