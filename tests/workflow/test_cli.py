"""Workflow CLI inference and status logging contracts."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

import pytest

import lclang
import lclang.workflow as wf
from lclang.cli import CliContext, CliParams, CliResultStatus
from lclang.errors import LclCliUsageError
from lclang.workflow.cli import cli_status, log_status_tree, status_lines


@dataclass
class ValueArgs:
    """One CLI-inferred input."""

    value: int


@dataclass
class ValueOutputs:
    """One CLI-inferred output."""

    value: int


@asynccontextmanager
async def local_value_context(
    context: wf.TaskContext,
    args: ValueArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> AsyncGenerator[ValueOutputs]:
    """Yield one task-local value.

    :param context: Current task context.
    :param args: Materialized context arguments.
    :param status_mgr: Context status manager.
    :returns: Async iterator yielding a local value.
    """
    del context, status_mgr
    yield ValueOutputs(args.value + 1)


@pytest.mark.asyncio
async def test_to_cli_infers_external_values_and_logs_tree_last(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only first-use externals reach help and status follows normal logs."""
    source = wf.define_variable[int]("source", is_masked=True)
    local = wf.define_variable[int]("local")
    produced = wf.define_variable[int]("produced")

    async def root_action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        """Publish one intermediate value.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Published intermediate output.
        """
        del status_mgr
        context.logger.info("normal action log")
        return ValueOutputs(args.value)

    async def child_action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        """Consume an internally published value.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Unpublished output.
        """
        del context, status_mgr
        return ValueOutputs(args.value + 1)

    context_task = wf.define_context_task(
        "local_context",
        "Local context",
        local_value_context,
        ValueArgs(source.quote),
        ValueOutputs(local.quote),
    )
    child = wf.define_task(
        "child",
        "Child",
        task_action=child_action,
        args_mapping=ValueArgs(produced.quote),
    )
    root = wf.define_task(
        "root",
        "Root",
        task_action=root_action,
        args_mapping=ValueArgs(local.quote),
        outputs_mapping=ValueOutputs(produced.quote),
        context_tasks=[context_task],
        children=[child],
    )
    command = wf.define_workflow("CLI workflow", root).to_cli("run", "Run it")

    assert [(item.name, item.description, item.masked) for item in command.parameter_docs] == [
        ("source", "NO HELP MESSAGE PROVIDED", True)
    ]
    logger = logging.getLogger("workflow-cli-test")
    params = CliParams("python", ("admin", "run"), date(2026, 8, 27), False, None, {})

    def choose_first(values: list[str]) -> str:
        return values[0]

    monkeypatch.setattr("lclang.workflow.cli_logging.random.choice", choose_first)
    async with lclang.define_frame(preset={"source": 5, "lunch.options": ["noodles"]}) as frame:
        context = CliContext(date(2026, 8, 27), False, frame, logger, params)
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await command.handler(context)

    assert result.result_status is CliResultStatus.SUCCESS
    messages = [record.getMessage() for record in caplog.records]
    assert "normal action log" in messages
    assert messages[-2].startswith("workflow complete: [admin.run] SUCCESS:\n")
    assert "   └─ [SUCCESS] child" in messages[-2]
    assert messages[-1] == "lunch option: noodles"


def test_failure_covered_cli_status_has_distinct_exit_code() -> None:
    """Covered failure remains independently observable by process callers."""
    assert int(CliResultStatus.FAILURE_COVERED) == 3


def test_cli_status_rendering_uses_details_connectors_and_severity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every process mapping and logging level has one stable representation."""
    tree = wf.ExecutionStatusTree(
        wf.ExecutionStatus.ERROR,
        wf.ExecutionTaskType.TASK,
        "workflow",
        "stopped",
        [
            wf.ExecutionStatusTree(
                wf.ExecutionStatus.FAILURE,
                wf.ExecutionTaskType.STEP,
                "expected",
                "rejected",
            ),
            wf.ExecutionStatusTree(
                wf.ExecutionStatus.FAILURE_COVERED,
                wf.ExecutionTaskType.TASK,
                "covered",
                "",
                [
                    wf.ExecutionStatusTree(
                        wf.ExecutionStatus.SUCCESS,
                        wf.ExecutionTaskType.STEP,
                        "cleanup",
                    )
                ],
            ),
        ],
    )
    assert status_lines(tree) == [
        "[ERROR] workflow: stopped",
        "├─ [FAILURE] expected: rejected",
        "└─ [FAILURE_COVERED] covered",
        "   └─ [SUCCESS] cleanup",
    ]
    logger = logging.getLogger("workflow-cli-levels")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_status_tree(logger, tree, "admin.run")
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
    assert caplog.records[0].getMessage() == (
        "workflow complete: [admin.run] ERROR:\n"
        "[ERROR] workflow: stopped\n"
        "├─ [FAILURE] expected: rejected\n"
        "└─ [FAILURE_COVERED] covered\n"
        "   └─ [SUCCESS] cleanup"
    )
    assert cli_status(wf.ExecutionStatus.FAILURE_COVERED) is CliResultStatus.FAILURE_COVERED
    assert cli_status(wf.ExecutionStatus.FAILURE) is CliResultStatus.FAILURE
    assert cli_status(wf.ExecutionStatus.ERROR) is CliResultStatus.EXCEPTION
    assert cli_status(wf.ExecutionStatus.SKIPPED) is CliResultStatus.SUCCESS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options, masked, failure, expected",
    [
        (["rice"], False, True, "lunch option: no lunch!"),
        ([], False, False, None),
        ("rice", False, False, None),
        ([1], False, False, None),
        (["secret"], True, False, None),
    ],
)
async def test_lunch_options_are_optional_and_never_change_status(
    options: object,
    masked: bool,
    failure: bool,
    expected: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only valid visible non-empty lists add a post-tree lunch record."""
    source = wf.define_variable[int]("source")

    async def action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        del context
        if failure:
            status_mgr.update(wf.ExecutionStatus.FAILURE, "rejected")
        return ValueOutputs(args.value)

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=ValueArgs(source.quote),
    )
    command = wf.define_workflow("Lunch", task).to_cli("run", "Run")
    key = "lunch.options!" if masked else "lunch.options"
    logger = logging.getLogger(f"workflow-lunch-{masked}-{failure}-{type(options).__name__}")
    params = CliParams("python", ("run",), date(2026, 8, 29), False, None, {})
    async with lclang.define_frame(preset={"source": 1, key: options}) as frame:
        context = CliContext(date(2026, 8, 29), False, frame, logger, params)
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await command.handler(context)

    assert result.result_status is (CliResultStatus.FAILURE if failure else CliResultStatus.SUCCESS)
    lunch = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("lunch option:")
    ]
    assert lunch == ([] if expected is None else [expected])


@pytest.mark.asyncio
async def test_failing_lunch_expression_is_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lunch evaluation errors never replace a successful workflow result."""
    source = wf.define_variable[int]("source")

    async def action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        del context, status_mgr
        return ValueOutputs(args.value)

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=ValueArgs(source.quote),
    )
    command = wf.define_workflow("Lunch", task).to_cli("run", "Run")
    module = lclang.Module(
        lclang.ModuleName("lunch-test"),
        {"lunch.options": lclang.parse_expression("missing_name")},
    )
    logger = logging.getLogger("workflow-lunch-evaluation-error")
    params = CliParams("python", ("run",), date(2026, 8, 29), False, None, {})
    async with lclang.define_frame(module, preset={"source": 1}) as frame:
        context = CliContext(date(2026, 8, 29), False, frame, logger, params)
        with caplog.at_level(logging.INFO, logger=logger.name):
            result = await command.handler(context)

    assert result.result_status is CliResultStatus.SUCCESS
    assert not any(record.getMessage().startswith("lunch option:") for record in caplog.records)


@pytest.mark.asyncio
async def test_to_cli_validates_presets_and_rejects_internal_overrides() -> None:
    """Only inferred external variables can enter the generated command Frame."""
    source = wf.define_variable[int]("source", "Source", is_masked=True)
    result = wf.define_variable[int]("result")

    async def action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        """Echo the external value.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Echoed result.
        """
        del context, status_mgr
        return ValueOutputs(args.value)

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=ValueArgs(source.quote),
        outputs_mapping=ValueOutputs(result.quote),
    )
    workflow = wf.define_workflow("Workflow", task)
    with pytest.raises(ValueError, match="non-external"):
        workflow.to_cli("run", "Run", {"result": 1})
    command = workflow.to_cli("run", "Run", {"source!": 2})
    assert command.preset == {"source": 2}
    assert command.masked_names == frozenset({"source"})

    logger = logging.getLogger("workflow-cli-invalid-override")
    params = CliParams(
        "python",
        ("run",),
        date(2026, 8, 27),
        False,
        None,
        {"result": "3"},
    )
    async with lclang.define_frame(preset={"source": 2}) as frame:
        context = CliContext(date(2026, 8, 27), False, frame, logger, params)
        with pytest.raises(LclCliUsageError, match="non-external"):
            await command.handler(context)


def test_to_cli_exposes_scoped_external_variables() -> None:
    """Qualified workflow inputs retain their exact names in generated help metadata."""
    source = wf.define_variable[int]("meter.start", "Opening meter reading")

    async def action(
        context: wf.TaskContext,
        args: ValueArgs,
        status_mgr: wf.ExecutionStatusManager,
    ) -> ValueOutputs:
        """Echo one scoped external value.

        :param context: Current task context.
        :param args: Materialized arguments.
        :param status_mgr: Current status manager.
        :returns: Echoed result.
        """
        del context, status_mgr
        return ValueOutputs(args.value)

    task = wf.define_task(
        "root",
        "Root",
        task_action=action,
        args_mapping=ValueArgs(source.quote),
    )
    command = wf.define_workflow("Workflow", task).to_cli("run", "Run")
    assert [(item.name, item.description) for item in command.parameter_docs] == [
        ("meter.start", "Opening meter reading")
    ]
