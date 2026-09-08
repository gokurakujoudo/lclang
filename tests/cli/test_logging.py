"""Layered logger configuration and CLI/Workflow output integration."""

import asyncio
import logging
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang import parse_expression
from lclang.cli import CliConfig, CliContext, CliParams, CliResult, cli
from lclang.cli.binding import build_binding
from lclang.cli.logger_config import logger_parameter
from lclang.diagnostics import internal_verbose_scope
from lclang.logger import LoggerHandlerConfig, resolve_logger_config

# Static configuration keeps test file inputs independent of runtime path creation.
LOGGER_SOURCE = """
__LCL_VERSION__: 1
logger.file.default.enabled: True
logger.file.default.level: "ERROR"
logger.file.default.rotation.mode: "size"
logger.file.default.rotation.max_bytes: 1048576
logger.file.app.filename: f"{__command__}.{{pid}}.log"
logger.file.audit.enabled: True
logger.file.audit.level: "WARNING"
logger.file.audit.rotation.max_bytes: 2097152
logger.console.level: "CRITICAL"
"""


@cli.command()
async def logger_command(context: CliContext) -> CliResult:
    """Emit one diagnostic and one command result."""
    context.logger.info("command-record")
    return CliResult.success("command-result")


def test_default_override_preserves_explicit_sink_fields() -> None:
    """A high-priority default closes app, while audit's explicit True survives."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "settings.lclcfg"
        path.write_text(LOGGER_SOURCE, encoding="utf-8")
        params = CliParams(
            "python",
            ("logger",),
            date.today(),
            False,
            str(path),
            {
                "logger.file.default.enabled": "LCL[False]",
                "logger.file.default.directory": directory,
                "logger.file.default.level": "DEBUG",
            },
        )

        async def exercise() -> None:
            binding = await build_binding(logger_command, params, CliConfig())
            try:
                config = await resolve_logger_config(binding.frame)
                sinks = config.resolved_files()
                assert not sinks["app"].enabled and sinks["audit"].enabled
                assert sinks["app"].level == 10 and sinks["audit"].level == 30
                assert sinks["app"].filename == "logger.{pid}.log"
                assert sinks["audit"].rotation.max_bytes == 2097152
                verbose = await resolve_logger_config(binding.frame, True)
                assert not verbose.resolved_files()["app"].enabled
                assert verbose.resolved_files()["audit"].level == 10
                assert verbose.resolved_console().level == 10
            finally:
                await binding.stack.close()

        asyncio.run(exercise())


def test_direct_sink_override_closes_explicit_exception(capsys: pytest.CaptureFixture[str]) -> None:
    """Direct False disables an explicit True and verbose cannot enable it."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "settings.lclcfg"
        path.write_text(LOGGER_SOURCE, encoding="utf-8")
        status = asyncio.run(
            logger_command.run(
                [
                    "python",
                    "tool.py",
                    "-c",
                    str(path),
                    "--verbose",
                    "-o",
                    "logger.file.default.enabled",
                    "LCL[False]",
                    "-o",
                    "logger.file.audit.enabled",
                    "LCL[False]",
                    "-o",
                    "logger.file.default.directory",
                    directory,
                ]
            )
        )
        assert status == 0
        assert list(Path(directory).glob("*.log")) == []
    output = capsys.readouterr()
    assert output.out == "command-result\n"
    assert "command-record" in output.err


@pytest.mark.parametrize(
    "key",
    [
        "logger.console.enabled",
        "logger.file.audit.enabled",
        "logger.level",
        "logger.file.default.rotation.interval",
    ],
)
def test_supported_logger_parameters(key: str) -> None:
    """Framework keys do not need workflow business variable declarations."""
    assert logger_parameter(key)


@pytest.mark.parametrize(
    "key",
    [
        "logger",
        "other.level",
        "logger.typo",
        "logger.file.audit.typo",
        "logger.file.audit.rotation.typo",
        "logger.file.audit",
        "logger.console.typo",
    ],
)
def test_unknown_logger_parameters(key: str) -> None:
    """The workflow exemption is schema-aware rather than prefix-only."""
    assert not logger_parameter(key)


def test_entry_defaults_retain_unset_fields() -> None:
    """Python defaults keep template fallback available to later overrides."""
    config = LoggerHandlerConfig(file={"default": {"enabled": False}, "app": {}})
    params = CliParams("python", ("logger",), date.today(), False, None, {})

    async def exercise() -> None:
        binding = await build_binding(logger_command, params, CliConfig(config))
        try:
            result = await resolve_logger_config(binding.frame)
            assert not result.resolved_files()["app"].enabled
        finally:
            await binding.stack.close()

    asyncio.run(exercise())


def test_runtime_parsing_retains_verbose_diagnostics() -> None:
    """Parsing performed after scope setup can still produce internal trace records."""
    with internal_verbose_scope(logging.getLogger(__name__)):
        assert parse_expression("1 + 2") is not None
