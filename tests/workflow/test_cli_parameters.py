"""Workflow input classification follows visible reads and writes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import lclang.workflow as wf
from lclang.cli import CliConfig, CliParams
from lclang.cli.binding import build_binding
from lclang.cli.help import render_command_help


@dataclass
class Values:
    """Arbitrary values used to test defaults without coercion."""

    value: object


async def echo(
    context: wf.TaskContext, args: Values, status_mgr: wf.ExecutionStatusManager,
) -> Values:
    """Echo the materialized value."""
    return args


@asynccontextmanager
async def local_value_context(
    context: wf.TaskContext, args: Values, status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[Values]:
    """Publish a value visible only inside this task."""
    yield args


@pytest.mark.parametrize("default", [None, False, 0, "", [], {}, abs])
def test_defaulted_read_before_write_is_optional(default: object) -> None:
    """Key presence distinguishes None and false values from an absent default."""
    value = wf.define_variable[object]("csv.value", "Value")
    task = wf.define_task(
        "root", "Root", task_action=echo,
        args_mapping=Values(value.quote), outputs_mapping=Values(value.quote),
    )
    workflow = wf.define_workflow("Example", task, lcl_mixin={"csv.value": 99, "helper": abs})
    command = workflow.to_cli("run", "Run", {"csv.value": default})
    assert [(item.name, item.required) for item in command.parameter_docs] == [("csv.value", False)]
    assert command.preset["csv.value"] is default
    assert "optional, default=" in render_command_help("tool.py", command, ("run",))


def test_read_write_order_and_context_visibility() -> None:
    """Local writes hide only local reads; global outputs reach later siblings."""
    source = wf.define_variable[int]("source")
    local = wf.define_variable[int]("local")
    produced = wf.define_variable[object]("produced")
    write_only = wf.define_variable[object]("write_only")
    context = wf.define_context_task(
        "context", "Context", local_value_context,
        Values(source.quote), Values(local.quote),
    )
    first = wf.define_task(
        "first", "First", task_action=echo, args_mapping=Values(local.quote),
        outputs_mapping=Values(produced.quote), context_tasks=[context],
    )
    second = wf.define_task(
        "second", "Second", task_action=echo, args_mapping=Values(produced.quote),
        outputs_mapping=Values(write_only.quote),
    )
    third = wf.define_task(
        "third", "Third", task_action=echo, args_mapping=Values(local.quote),
    )
    root = wf.define_task(
        "root", "Root", task_action=echo, args_mapping=Values(source.quote),
        children=[first, second, third],
    )
    command = wf.define_workflow("Example", root).to_cli("run", "Run")
    assert [(item.name, item.required) for item in command.parameter_docs] == [
        ("source", True), ("local", True),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,overrides,expected",
    [
        (None, {}, None),
        ("csv.value: 7\n", {}, 7),
        ("csv.value: 7\n", {"csv.value": "LCL[9]"}, 9),
    ],
)
async def test_scoped_defaults_remain_below_config_and_overrides(
    source: str | None, overrides: dict[str, str | bool], expected: object,
) -> None:
    """Displaying a default does not promote its runtime binding priority."""
    value = wf.define_variable[object]("csv.value", "Value")
    task = wf.define_task("root", "Root", task_action=echo, args_mapping=Values(value.quote))
    workflow = wf.define_workflow("Example", task, lcl_mixin={"csv.value": None})
    command = workflow.to_cli("run", "Run")
    assert not command.parameter_docs[0].required
    assert "default=None" in render_command_help("tool.py", command, ("run",))
    with TemporaryDirectory() as directory:
        path = None
        if source is not None:
            path = Path(directory) / "input.lclcfg"
            path.write_text(source, encoding="utf-8")
        params = CliParams(
            "python", ("run",), date(2026, 9, 21), False,
            None if path is None else str(path), overrides,
        )
        binding = await build_binding(command, params, CliConfig())
        try:
            assert await binding.frame.get("csv.value") == expected
        finally:
            await binding.stack.close()
