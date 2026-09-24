"""Entrance host defaults across plain commands and workflow tasks."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

import lclang.workflow as wf
from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, ParameterDoc, cli

# Static config exercises application and logger expressions before handler execution.
CONFIG = "value: helper(seed)\nlogger.console.enabled: console_on\n"


@dataclass
class Value:
    """One mapped workflow input and output."""

    value: int


@pytest.mark.asyncio
async def test_entrance_defaults_reach_all_commands_configs_and_tasks() -> None:
    """Nested routes retain local precedence and fresh state on repeated invocations."""
    observed: list[int] = []

    @cli.command(parameter_docs=[ParameterDoc("value", int, True, "Value")], preset={"seed": -3})
    async def plain_command(context: CliContext) -> CliResult:
        assert await context.frame.get("helper") is abs
        assert context.frame.is_masked("seed")
        assert not context.frame.has("touched")
        context.frame.mixin({"touched": True})
        observed.append(cast(int, await context.frame.get("value")))
        return CliResult.success("")

    async def action(
        context: wf.TaskContext,
        args: Value,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Value:
        del status_mgr
        assert await context.frame.get("helper") is abs
        assert context.frame.is_masked("seed")
        observed.append(args.value)
        return args

    workflow = wf.define_workflow(
        "Workflow",
        wf.define_task(
            "task",
            "Task",
            task_action=action,
            args_mapping=Value(wf.define_variable[int]("value").quote),
        ),
        lcl_mixin={"seed": -5},
    )
    workflow_command = workflow.to_cli("work", "Work")
    group = CommandGroup(
        "root",
        "Root",
        [
            plain_command,
            CommandGroup("nested", "Nested", [workflow_command]),
        ],
    )
    supplied: dict[str, object] = {
        "helper": abs,
        "seed!": -7,
        "value": 1,
        "console_on": False,
    }
    entrance = CliEntrance(group, lcl_mixin=supplied)
    supplied["value"] = 100
    with pytest.raises(TypeError):
        cast(dict[str, object], entrance.lcl_mixin)["value"] = 200
    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.lclcfg"
        path.write_text(CONFIG, encoding="utf-8")
        for route, configured in [(["plain"], 3), (["nested", "work"], 5)]:
            for options, expected in [
                ([], 1),
                (["-c", str(path)], configured),
                (["-c", str(path), "-o", "value", "LCL[9]"], 9),
                ([], 1),
            ]:
                assert await entrance.run(["python", "tool.py", *route, *options]) == 0
                assert observed[-1] == expected
        other = CliEntrance(group, lcl_mixin={**supplied, "value": 22})
        assert await other.run(["python", "tool.py", "plain"]) == 0
        assert observed[-1] == 22
    assert dict(plain_command.preset) == {"seed": -3}
    assert dict(workflow_command.preset) == {"seed": -5}
    assert plain_command.masked_names == workflow_command.masked_names == frozenset()


@pytest.mark.parametrize("bindings", [{"": 1}, {"a": 1, "a.b": 2}, {"a": 1, "a!": 2}])
def test_entrance_rejects_invalid_host_bindings(bindings: dict[str, object]) -> None:
    """Binding failures are reported while defining the entrance."""
    with pytest.raises(ValueError):
        CliEntrance(CommandGroup("root", "Root", []), lcl_mixin=bindings)
