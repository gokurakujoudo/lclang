"""Workflow defaults integrate with CLI precedence and side-effect-free help."""

from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

import lclang.workflow as wf
from lclang.cli import CliConfig, CliParams
from lclang.cli.binding import build_binding
from lclang.cli.help import render_command_help
from tests.workflow.default_support import Value, execution_context, workflow_for


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("default", 3),
        ("preset", 5),
        ("config", 7),
        ("override", 9),
    ],
)
async def test_cli_default_precedence(source: str, expected: int) -> None:
    """Lowest fallback does not disturb existing configuration and CLI precedence."""
    workflow = workflow_for(wf.define_variable[object]("value", default=3))
    command = workflow.to_cli("run", "Run", None if source == "default" else {"value": 5})
    with TemporaryDirectory() as directory:
        config = Path(directory) / "config.lclcfg"
        config.write_text("value: 7\ncalculated: value * 2\n", encoding="utf-8")
        params = CliParams(
            "python",
            ("run",),
            date(2026, 9, 22),
            False,
            str(config) if source in {"config", "override"} else None,
            {"value": "LCL[9]"} if source == "override" else {},
        )
        binding = await build_binding(command, params, CliConfig())
        try:
            result = await workflow.execute(execution_context(binding.frame))
            assert result.task_args[wf.TaskID("root")] == Value(expected)
        finally:
            await binding.stack.close()


@pytest.mark.asyncio
async def test_cli_factory_is_not_invoked_by_help_or_binding_creation() -> None:
    """Execution and LCL share the invocation's one lazy factory result."""
    calls: list[object] = []

    def factory() -> object:
        value = object()
        calls.append(value)
        return value

    workflow = workflow_for(wf.define_variable[object]("value", default_factory=factory))
    command = workflow.to_cli("run", "Run")
    assert "default=<factory>" in render_command_help("tool", command, ("run",))
    assert not calls
    params = CliParams("python", ("run",), date(2026, 9, 22), False, None, {})
    binding = await build_binding(command, params, CliConfig())
    try:
        assert not calls
        value = await binding.frame.evaluate("value")
        result = await workflow.execute(execution_context(binding.frame))
        assert cast(Value, result.task_args[wf.TaskID("root")]).value is value is calls[0]
        assert len(calls) == 1
    finally:
        await binding.stack.close()
    for value in (None, 3):
        literal = workflow_for(
            wf.define_variable[object]("value", default=value),
        ).to_cli("run", "Run")
        assert f"default={value!r}" in render_command_help("tool", literal, ("run",))
    secret = workflow_for(
        wf.define_variable[object]("value", is_masked=True, default="secret"),
    ).to_cli("run", "Run")
    assert "secret" not in render_command_help("tool", secret, ("run",))
    assert "default=8" in render_command_help(
        "tool",
        replace(command, preset={"value": 8}),
        ("run",),
    )
