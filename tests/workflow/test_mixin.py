"""Workflow host-binding snapshots and runtime integration."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

import lclang
import lclang.workflow as wf
from lclang.cli import CliConfig, CliContext, CliParams, CliResultStatus
from lclang.cli.binding import build_binding


@dataclass
class Value:
    """One mapped input or output."""

    value: int


async def echo(
    context: wf.TaskContext,
    args: Value,
    status_mgr: wf.ExecutionStatusManager,
) -> Value:
    """Return the mapped value after checking direct host access."""
    del status_mgr
    assert await context.frame.get("helper") is abs
    return args


def task() -> wf.TaskNode:
    """Build one config-consuming task."""
    return wf.define_task(
        "root",
        "Root",
        task_action=echo,
        args_mapping=Value(wf.define_variable[int]("value").quote),
        outputs_mapping=Value(wf.define_variable[int]("result").quote),
    )


@pytest.mark.asyncio
async def test_mixin_snapshot_config_tasks_and_concurrent_runs() -> None:
    """Reusable snapshots override inputs without sharing per-run outputs."""
    supplied: dict[str, object] = {"helper": abs, "seed!": -4}
    workflow = wf.define_workflow("Example", task(), lcl_mixin=supplied)
    supplied["seed!"] = -100
    with pytest.raises(TypeError):
        cast(dict[str, object], workflow.lcl_mixin)["seed!"] = -50

    async def run(index: int) -> None:
        module = lclang.define_module("config", {"value": "helper(seed) + index"})
        async with lclang.define_frame(module, preset={"seed": -20, "index": index}) as frame:
            context = wf.WorkflowExecutionContext(
                False,
                date(2026, 9, 19),
                False,
                logging.getLogger("mixin"),
                frame,
            )
            result = await workflow.execute(context)
            assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
            assert result.execution_frame is frame
            assert await frame.get("result") == 4 + index
            assert await frame.get("seed") == -4
            assert frame.is_masked("seed")

    await asyncio.gather(*(run(index) for index in range(32)))


@pytest.mark.parametrize("bindings", [{"": 1}, {"a": 1, "a.b": 2}, {"a": 1, "a!": 2}])
def test_invalid_mixin_names_fail_at_definition(bindings: dict[str, object]) -> None:
    """Invalid or ambiguous host bindings never reach execution."""
    with pytest.raises(ValueError):
        wf.define_workflow("Example", task(), lcl_mixin=bindings)


@pytest.mark.asyncio
@pytest.mark.parametrize("override, expected", [({}, 7), ({"value": "LCL[9]"}, 9)])
async def test_cli_mixin_available_to_config_and_preserves_overrides(
    override: dict[str, str | bool],
    expected: int,
) -> None:
    """CLI builds host helpers before evaluating config and retains precedence."""
    workflow = wf.define_workflow(
        "Example",
        task(),
        lcl_mixin={"helper": abs, "seed!": -7, "value": 1},
    )
    command = workflow.to_cli("example", "Example", preset={"value": 2})
    assert command.preset["value"] == 2
    assert [item.name for item in command.parameter_docs] == ["value"]
    source = "__LCL_VERSION__: 1\nvalue: helper(seed)\n"
    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.lclcfg"
        path.write_text(source, encoding="utf-8")
        params = CliParams("python", ("example",), date(2026, 9, 19), False, str(path), override)
        binding = await build_binding(command, params, CliConfig())
        try:
            assert await binding.frame.get("value") == expected
            assert binding.frame.is_masked("seed")
            result = await command.handler(
                CliContext(
                    params.as_of_date,
                    False,
                    binding.frame,
                    logging.getLogger("mixin-cli"),
                    params,
                )
            )
            assert result.result_status is CliResultStatus.SUCCESS
            assert await binding.frame.get("result") == expected
        finally:
            await binding.stack.close()
