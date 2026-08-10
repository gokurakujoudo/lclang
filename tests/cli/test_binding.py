"""Behavioural tests for layered CLI Frame construction and ownership."""

import asyncio
from datetime import date
from typing import cast

import pytest

from pylcl.cli import (
    CliConfig,
    CliContext,
    CliParams,
    CliResult,
    CliResultStatus,
    ParameterDoc,
    cli,
)
from pylcl.cli.binding import FrameStack, build_binding, default_definitions
from pylcl.errors import LclCliUsageError
from pylcl.runtime import Frame, VariableInspectionStatus


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
    assert asyncio.run(binding.frame.get("as_of_date")) == date(2026, 8, 9)
    asyncio.run(binding.stack.close())
    asyncio.run(binding.stack.close())
    definitions = default_definitions(bound_command, CliConfig())
    assert "optional_value" not in definitions
    assert "log_format" in definitions


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
        assert await binding.frame.get("cli_params") is params
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
