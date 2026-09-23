"""Workflow-to-CLI inference, execution, and status logging."""

from __future__ import annotations

from dataclasses import replace

from lclang.cli import CliContext, CliResult, CliResultStatus, Command, ParameterDoc
from lclang.cli.logger_config import logger_parameter
from lclang.errors import LclCliUsageError
from lclang.masking import normalize_masked_mapping
from lclang.workflow.cli_logging import log_lunch_option, log_status_tree, status_lines
from lclang.workflow.cli_parameters import expand_record_parameters
from lclang.workflow.context import WorkflowExecutionContext
from lclang.workflow.defaults import workflow_defaults
from lclang.workflow.definitions import Workflow
from lclang.workflow.mappings.dependencies import external_uses, has_field_default
from lclang.workflow.mappings.records import can_construct_record
from lclang.workflow.models import ExecutionStatus
from lclang.workflow.projections import TaskProjection
from lclang.workflow.variables import TaskVar

# Stable help used when an external variable omits its description.
# Unitless fallback prose below is the existing workflow help contract. Its explicit wording
# exposes an absent description rather than inventing documentation for inferred parameters.
NO_HELP_MESSAGE = "NO HELP MESSAGE PROVIDED"
# Compatibility exports for final workflow CLI rendering helpers.
__all__ = ["cli_status", "log_status_tree", "status_lines", "workflow_command"]


def external_variables(workflow: Workflow) -> tuple[TaskVar[object], ...]:
    """Infer variables read before a visible workflow assignment.

    :param workflow: Workflow definition to analyze.
    :returns: External variables in first-use order.
    """
    external: dict[str, TaskVar[object]] = {}
    for node in external_uses(workflow):
        variable = node.value.root if isinstance(node.value, TaskProjection) else node.value
        external.setdefault(variable.name, variable)
    return tuple(external.values())


def cli_status(status: ExecutionStatus) -> CliResultStatus:
    """Map one finalized workflow status to a process result.

    :param status: Final execution status.
    :returns: Corresponding CLI result status.
    """
    if status is ExecutionStatus.FAILURE_COVERED:
        return CliResultStatus.FAILURE_COVERED
    if status is ExecutionStatus.FAILURE:
        return CliResultStatus.FAILURE
    if status is ExecutionStatus.ERROR:
        return CliResultStatus.EXCEPTION
    return CliResultStatus.SUCCESS


def workflow_command(
    workflow: Workflow,
    name: str,
    summary: str,
    preset: dict[str, object] | None,
) -> Command:
    """Create one CLI command from inferred workflow inputs.

    :param workflow: Workflow definition to execute.
    :param name: Command name.
    :param summary: Human-readable summary.
    :param preset: Optional external-variable defaults.
    :returns: Immutable executable command.
    :raises LclCliUsageError: Through the handler for an unknown override.
    :raises ValueError: If a preset targets a non-external variable.
    """
    variables = external_variables(workflow)
    values, preset_masks = normalize_masked_mapping({} if preset is None else preset)
    supplied_names = set(values)
    mixin_values, mixin_masks = normalize_masked_mapping(workflow.lcl_mixin)
    values = {**mixin_values, **values}
    preset_masks |= mixin_masks
    execution_workflow = replace(workflow, lcl_mixin={})
    defaults = workflow_defaults(workflow)
    default_names = {name.removesuffix("!") for name in defaults}
    required_names = {
        node.value.name for node in external_uses(workflow) if not has_field_default(node)
    }
    docs = expand_record_parameters(tuple(
        ParameterDoc(
            item.name,
            item.value_type,
            item.name in required_names and item.name not in values.keys() | default_names
            and not can_construct_record(item.value_type),
            item.description or NO_HELP_MESSAGE,
            masked=item.is_masked or item.name in preset_masks,
        )
        for item in variables
    ))
    allowed = {item.name for item in docs}
    if supplied_names - allowed:
        raise ValueError("workflow preset contains non-external variable")
    masked = preset_masks | {
        item.name for item in variables if item.is_masked and item.name in values
    }

    async def handler(context: CliContext) -> CliResult:
        """Execute the captured workflow through one CLI invocation.

        :param context: Current CLI invocation.
        :returns: Empty logger-only workflow result.
        :raises LclCliUsageError: If an override is not an external variable.
        """
        unknown = {
            name
            for name in context.raw_params.overrides
            if name not in allowed and not logger_parameter(name)
        }
        if unknown:
            raise LclCliUsageError("workflow override targets non-external variable")
        result = await execution_workflow.execute(
            WorkflowExecutionContext(
                context.dryrun,
                context.as_of_date,
                context.raw_params.verbose,
                context.logger,
                context.frame,
            )
        )
        workflow_id = ".".join(context.raw_params.command)
        log_status_tree(context.logger, result.execution_status, workflow_id)
        await log_lunch_option(
            context.logger,
            context.frame,
            result.execution_status.status,
        )
        return CliResult(cli_status(result.execution_status.status), "")

    return Command(
        name,
        summary,
        docs,
        values,
        handler,
        masked_names=frozenset(masked),
        default_bindings=defaults,
    )
