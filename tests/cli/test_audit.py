"""Behavioural tests for the readable CLI audit preamble."""

import asyncio
import io
import logging
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import lclang
from lclang.cli import CliConfig, CliContext, CliParams, CliResult, LogConfig, ParameterDoc, cli
from lclang.cli.audit import normalized_argv, selected_binding
from lclang.cli.binding import build_binding
from lclang.cli.logging import LoggerHandle, log_execution_start
from lclang.runtime import VariableInspectionStatus


@cli.command(
    parameter_docs=(
        ParameterDoc("message", str, True, "Message"),
        ParameterDoc("token", str, True, "Token", masked=True),
    )
)
async def audit_command(context: CliContext) -> CliResult:
    """Return without evaluating the audit fixture.

    :param context: Current invocation.
    :returns: Empty successful result.
    """
    del context
    return CliResult.success("")


def test_audit_preamble_is_readable_redacted_and_non_evaluating() -> None:
    """Raw argv, winning definitions, host values, and masks render without lookup."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config_path = root / "audit.lclcfg"
        config_path.write_text(
            'prefix: "hello "\n'
            'group.value: 1\n'
            'message: prefix + "config"\n'
            'stored!: "file-secret"\n'
            'token!: "config-secret"\n',
            encoding="utf-8",
        )
        raw_argv = (
            "python",
            "tool.py",
            "audit",
            "-o",
            "token",
            "cli-secret",
            "-c",
            str(config_path),
            "-o",
            "message",
            'LCL[prefix + "override"]',
            "-wif",
        )
        params = CliParams(
            "python",
            ("audit",),
            date(2026, 8, 29),
            True,
            str(config_path),
            {"token": "cli-secret", "message": 'LCL[prefix + "override"]'},
            raw_argv=raw_argv,
            script_path="tool.py",
        )
        binding = asyncio.run(build_binding(audit_command, params, CliConfig()))
        stream = io.StringIO()
        logger = logging.Logger("audit-test", logging.INFO)
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        handle = LoggerHandle(logger, (handler,), root / "audit.log")
        try:
            log_execution_start(
                handle,
                params,
                binding.frame,
                binding.execution_config_names,
            )
            assert (
                binding.frame.inspect_variable("message").status
                is VariableInspectionStatus.NOT_EVALUATED
            )
            assert selected_binding(binding.frame, "group") is None
            assert selected_binding(binding.frame, "absent") is None
        finally:
            handle.close()
            asyncio.run(binding.stack.close())

    messages = stream.getvalue().splitlines()
    assert messages[:3] == [
        f"execution log file path: {root / 'audit.log'}",
        "execution started:",
        "===================================================",
    ]
    assert "==                     audit                     ==" in messages
    assert "==             As-of Date: 2026-08-29            ==" in messages
    assert "==                Dryrun Mode: ON                ==" in messages
    assert "==               Verbose Mode: OFF               ==" in messages
    command_line = next(line for line in messages if line.startswith("execution command line:"))
    assert '"-o", "token", "*masked*", "-c"' in command_line
    assert '"-wif"' in command_line
    assert "cli-secret" not in stream.getvalue()
    config_at = messages.index("execution config:")
    assert messages[config_at + 1 :] == [
        "    group.value: 1",
        "    message    : prefix + 'override'",
        "    prefix     : 'hello '",
        "    stored     : *masked*",
        "    token      : (str) *masked*",
    ]


def test_default_log_format_does_not_render_logging_args() -> None:
    """The public default ends with the rendered message."""
    config = LogConfig()
    assert "%(args)" not in config.log_format


def test_manual_params_reconstruct_a_redacted_argv_fallback() -> None:
    """Legacy manually constructed params retain deterministic audit argv."""
    params = CliParams(
        "python",
        ("run",),
        date(2026, 8, 29),
        True,
        "settings.lclcfg",
        {"token": "secret", "enabled": True},
        True,
        script_path="tool.py",
    )
    frame = lclang.define_frame(preset={"token!": "secret"})
    try:
        assert normalized_argv(params, frame) == [
            "python",
            "tool.py",
            "run",
            "--config",
            "settings.lclcfg",
            "--override",
            "token",
            "*masked*",
            "--override",
            "enabled",
            "--as-of",
            "20260829",
            "--dryrun",
            "--verbose",
        ]
    finally:
        asyncio.run(frame.close())
