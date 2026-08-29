"""Behavioural tests for isolated CLI logger construction."""

import asyncio
import logging
import re
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import lclang
from lclang.cli import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_COMMAND_KEY,
    RUNTIME_DRYRUN_KEY,
    RUNTIME_EXECUTION_TIMESTAMP_KEY,
    RUNTIME_VERBOSE_KEY,
    RUNTIME_YMD_KEY,
    CliConfig,
    CliContext,
    CliParams,
    CliResult,
    CliResultStatus,
    LogConfig,
    cli,
)
from lclang.cli.binding import build_binding
from lclang.cli.console_logging import attach_console_handlers
from lclang.cli.logging import (
    build_handler,
    create_logger,
    create_verbose_logger,
    log_execution_start,
    normalized_argv,
    numeric_log_level,
    redacted_overrides,
    resolve_log_config,
)
from lclang.diagnostics import internal_trace, internal_verbose_scope

# Static configuration source proving logger fields resolve beneath one scope.
SCOPED_LOG_CONFIG_SOURCE = (
    'logger.log_file_name: f"{'
    + RUNTIME_COMMAND_KEY
    + '}-{'
    + RUNTIME_YMD_KEY
    + '}-{'
    + RUNTIME_EXECUTION_TIMESTAMP_KEY
    + '}.log"\n'
    + 'logger.log_level: "DEBUG" if '
    + RUNTIME_VERBOSE_KEY
    + " and "
    + RUNTIME_DRYRUN_KEY
    + ' else "INFO"\n'
)


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
    assert handle.log_path is None
    log_execution_start(handle, params, binding.frame)
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


def test_console_and_file_handlers_share_the_configured_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stdout, stderr, and the enabled file render records identically."""
    with TemporaryDirectory() as directory:
        module = lclang.define_module("shared-log-format", {})
        frame = lclang.define_frame(
            module,
            preset={
                "logger.log_dir": directory,
                "logger.log_file_name": "shared.log",
                "logger.log_level": "DEBUG",
                "logger.log_format": (
                    "%(asctime)s|%(levelname)s|%(filename)s:%(lineno)d|"
                    "%(funcName)s|%(message)s|%(args)r"
                ),
            },
        )

        async def exercise() -> None:
            """Emit records through one shared invocation logger."""
            handle = await create_logger(frame, "shared")
            try:
                attach_console_handlers(handle, False)
                handle.logger.info("visible=%s", "stdout")
                handle.logger.error("visible=%s", "stderr")
            finally:
                handle.close()
                await frame.close()

        asyncio.run(exercise())
        captured = capsys.readouterr()
        file_lines = (Path(directory) / "shared.log").read_text(
            encoding="utf-8"
        ).splitlines()
        assert captured.out.splitlines() == [file_lines[0]]
        assert captured.err.splitlines() == [file_lines[1]]


def test_scoped_logger_config_overrides_framework_defaults() -> None:
    """Configuration logger leaves replace matching scoped defaults."""
    with TemporaryDirectory() as directory:
        config_path = Path(directory) / "logger.lclcfg"
        config_path.write_text(SCOPED_LOG_CONFIG_SOURCE, encoding="utf-8")
        params = CliParams(
            "python",
            ("logger",),
            date(2026, 8, 27),
            True,
            str(config_path),
            {},
            True,
        )

        async def exercise() -> None:
            """Resolve scoped logger configuration in one event loop."""
            binding = await build_binding(
                logger_command,
                params,
                CliConfig(LogConfig(log_dir=directory)),
            )
            try:
                timestamp = await binding.frame.get(RUNTIME_EXECUTION_TIMESTAMP_KEY)
                assert isinstance(timestamp, str)
                assert re.fullmatch(r"\d{14}", timestamp)
                assert await binding.frame.get(RUNTIME_YMD_KEY) == "20260827"
                assert await binding.frame.get(RUNTIME_COMMAND_KEY) == "logger"
                assert await binding.frame.get(RUNTIME_AS_OF_DATE_KEY) == date(2026, 8, 27)
                assert await binding.frame.get(RUNTIME_DRYRUN_KEY) is True
                assert await binding.frame.get(RUNTIME_VERBOSE_KEY) is True
                assert await resolve_log_config(binding.frame) == LogConfig(
                    log_dir=directory,
                    log_file_name=f"logger-20260827-{timestamp}.log",
                    log_level="DEBUG",
                )
            finally:
                await binding.stack.close()

        asyncio.run(exercise())


def test_normalized_argv_retains_valueless_and_verbose_options() -> None:
    """Canonical audit argv omits values for Boolean overrides and optional paths."""
    params = CliParams(
        "python",
        ("logger",),
        date(2026, 8, 27),
        False,
        None,
        {"enabled": True},
        True,
        script_path="tool.py",
    )
    binding = asyncio.run(build_binding(logger_command, params, CliConfig()))
    try:
        assert redacted_overrides(params, binding.frame) == {"enabled": True}
        assert normalized_argv(params, binding.frame) == [
            "python",
            "tool.py",
            "logger",
            "--override",
            "enabled",
            "--as-of",
            "20260827",
            "--verbose",
        ]
    finally:
        asyncio.run(binding.stack.close())


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
                "logger.log_dir": directory,
                "logger.log_file_name": "audit.log",
                "logger.log_level": "INFO",
                "logger.log_format": (
                    "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s "
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
