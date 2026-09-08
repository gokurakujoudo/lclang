"""Behavioural tests for layered CLI Frame construction and ownership."""

import asyncio
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

import lclang
from lclang.cli import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_CLI_PARAMS_KEY,
    CliConfig,
    CliContext,
    CliParams,
    CliResult,
    CliResultStatus,
    ParameterDoc,
    cli,
)
from lclang.cli.binding import FrameStack, build_binding, default_definitions
from lclang.errors import LclCliUsageError
from lclang.runtime import Frame, VariableInspectionStatus
from lclang.utils.environment import BoundEnvironment


@cli.command(
    parameter_docs=[
        ParameterDoc("required_value", str, True, "required", "default"),
        ParameterDoc("optional_value", str, False, "optional"),
    ]
)
async def bound_command(context: CliContext) -> CliResult:
    """Return a reusable binding result.

    :param context: Current invocation.
    :returns: Successful result.
    """
    return CliResult(CliResultStatus.SUCCESS, str(await context.frame.get("required_value")))


def test_default_binding_is_lazy_and_closes_idempotently() -> None:
    """Defaults and runtime values resolve without a config file."""
    params = CliParams("python", ("bound",), date(2026, 8, 9), False, None, {})
    binding = asyncio.run(build_binding(bound_command, params, CliConfig()))
    assert asyncio.run(binding.frame.get("required_value")) == "default"
    assert asyncio.run(binding.frame.get(RUNTIME_AS_OF_DATE_KEY)) == date(2026, 8, 9)
    assert binding.frame.has("as_of_date") is False
    assert binding.frame.has("dryrun") is False
    asyncio.run(binding.stack.close())
    asyncio.run(binding.stack.close())
    definitions = default_definitions(bound_command, CliConfig())
    assert "optional_value" not in definitions
    assert "logger.format" in definitions
    assert "log_format" not in definitions


def test_marked_command_defaults_and_presets_reach_effective_frame_policy() -> None:
    """Every declared CLI binding source retains normalized sticky masking."""
    @cli.command(
        parameter_docs=[ParameterDoc("token!", str, True, "secret", "default-secret")],
        preset={"imported!": "preset-secret"},
    )
    async def masked_command(context: CliContext) -> CliResult:
        """Return an empty result.

        :param context: Current invocation.
        :returns: Successful result.
        """
        return CliResult.success("")

    params = CliParams("python", ("masked",), date.today(), False, None, {})
    binding = asyncio.run(build_binding(masked_command, params, CliConfig()))
    try:
        assert binding.frame.is_masked("token") is True
        assert binding.frame.is_masked("imported") is True
        assert asyncio.run(binding.frame.get("token")) == "default-secret"
        assert asyncio.run(binding.frame.get("imported")) == "preset-secret"
    finally:
        asyncio.run(binding.stack.close())


def test_missing_required_parameter_is_a_usage_error() -> None:
    """Presence checks do not need to evaluate any configuration value."""

    @cli.command(parameter_docs=[ParameterDoc("missing", str, True, "missing")])
    async def missing_command(context: CliContext) -> CliResult:
        """Return an unreachable result.

        :param context: Current invocation.
        :returns: Unreachable result.
        """
        return CliResult(CliResultStatus.SUCCESS, "")

    params = CliParams("python", ("missing",), date.today(), False, None, {})
    with pytest.raises(LclCliUsageError, match="missing required"):
        asyncio.run(build_binding(missing_command, params, CliConfig()))


@pytest.mark.asyncio
async def test_literal_overrides_are_host_values_beside_lazy_definitions() -> None:
    """Literal and malformed tokens stay external while valid markers remain lazy."""
    params = CliParams(
        "python",
        ("bound",),
        date(2026, 8, 9),
        False,
        None,
        {
            "enabled": True,
            "literal": "100",
            "malformed": "LCL[bad +]",
            "expression": "LCL[literal + 'x']",
        },
    )
    binding = await build_binding(bound_command, params, CliConfig())
    try:
        literal = binding.frame.inspect_variable("literal")
        malformed = binding.frame.inspect_variable("malformed")
        expression = binding.frame.inspect_variable("expression")
        enabled = binding.frame.inspect_variable("enabled")
        assert enabled.status is VariableInspectionStatus.EXTERNAL_PROVIDED
        assert enabled.current_value is True
        assert await binding.frame.get("enabled") is True
        assert literal.status is VariableInspectionStatus.EXTERNAL_PROVIDED
        assert literal.current_value == "100"
        assert malformed.status is VariableInspectionStatus.EXTERNAL_PROVIDED
        assert malformed.current_value == "LCL[bad +]"
        assert expression.status is VariableInspectionStatus.NOT_EVALUATED
        assert await binding.frame.get("expression") == "100x"
        assert await binding.frame.get(RUNTIME_CLI_PARAMS_KEY) is params
        assert binding.frame.has("cli_params") is False
    finally:
        await binding.stack.close()


@pytest.mark.asyncio
async def test_scoped_cli_overrides_share_one_proxy() -> None:
    """Literal, lazy, and marker overrides compose through qualified lookup."""
    params = CliParams(
        "python",
        ("bound",),
        date(2026, 8, 9),
        False,
        None,
        {
            "A": "LCL[FRAME_PROXY]",
            "A.x": "40",
            "A.y": "LCL[int(A.x) + 2]",
        },
    )
    binding = await build_binding(bound_command, params, CliConfig())
    try:
        assert await binding.frame.get("A.y") == 42
        assert isinstance(await binding.frame.get("A"), lclang.FrameProxy)
    finally:
        await binding.stack.close()


@pytest.mark.asyncio
async def test_cli_overrides_select_dynamic_using_targets() -> None:
    """The same lazy CLI override selects a source and wins in the final Frame."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        config_path = root / "root.lclcfg"
        config_path.write_text(
            'choice: "blue"\nusing f"{choice}.lclcfg"\n',
            encoding="utf-8",
        )
        (root / "blue.lclcfg").write_text(
            'required_value: "blue"\n', encoding="utf-8"
        )
        (root / "green.lclcfg").write_text(
            'required_value: "green"\n', encoding="utf-8"
        )
        params = CliParams(
            "python",
            ("bound",),
            date(2026, 8, 9),
            False,
            str(config_path),
            {"choice": "LCL['green']"},
        )
        binding = await build_binding(bound_command, params, CliConfig())
        try:
            assert await binding.frame.get("choice") == "green"
            assert await binding.frame.get("required_value") == "green"
        finally:
            await binding.stack.close()


@pytest.mark.asyncio
async def test_cli_environment_override_does_not_mutate_process_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lazy explicit None wins over a live environment value only in the Frame."""
    name = "LCLANG_CLI_ENV_TEST"
    monkeypatch.setenv(name, "system")
    params = CliParams(
        "python",
        ("bound",),
        date(2026, 8, 9),
        False,
        None,
        {f"env.{name}": "LCL[None]"},
    )
    binding = await build_binding(bound_command, params, CliConfig())
    try:
        environment = await binding.frame.get("env")
        assert isinstance(environment, BoundEnvironment)
        assert await environment.get(name, "fallback") is None
        assert os.environ[name] == "system"
    finally:
        await binding.stack.close()


class CloseProbe:
    """Record close calls and optionally fail.

    :param failure: Optional message raised during close.
    """

    def __init__(self, failure: str | None) -> None:
        """Create one close probe.

        :param failure: Optional message raised during close.
        :returns: ``None``.
        """
        self.failure = failure
        self.calls = 0

    async def close(self) -> None:
        """Record one close and optionally fail.

        :returns: ``None``.
        :raises RuntimeError: If failure was requested.
        """
        self.calls += 1
        if self.failure is not None:
            raise RuntimeError(self.failure)


def test_frame_stack_continues_reverse_cleanup_after_failure() -> None:
    """The first cleanup failure is retained while every Frame is attempted."""
    first = CloseProbe(None)
    second = CloseProbe("close failed")
    stack = FrameStack((cast(Frame, first), cast(Frame, second)))
    with pytest.raises(RuntimeError, match="close failed"):
        asyncio.run(stack.close())
    assert first.calls == second.calls == 1
    asyncio.run(stack.close())


def test_frame_stack_retains_first_of_multiple_close_failures() -> None:
    """Reverse cleanup attempts every Frame and raises its first encountered failure."""
    first = CloseProbe("first failed")
    second = CloseProbe("second failed")
    stack = FrameStack((cast(Frame, first), cast(Frame, second)))
    with pytest.raises(RuntimeError, match="second failed"):
        asyncio.run(stack.close())
    assert first.calls == second.calls == 1
