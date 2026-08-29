"""Workflow-to-CLI inference, execution, and status logging."""

from __future__ import annotations

from lclang.cli import CliContext, CliResult, CliResultStatus, Command, ParameterDoc
from lclang.errors import LclCliUsageError
from lclang.masking import normalize_masked_mapping
from lclang.workflow.cli_logging import log_lunch_option, log_status_tree, status_lines
from lclang.workflow.context import WorkflowExecutionContext
from lclang.workflow.definitions import TaskNode, Workflow
from lclang.workflow.mappings import mapping_variables
from lclang.workflow.models import ExecutionStatus
from lclang.workflow.variables import TaskVar

# Stable help used when an external variable omits its description.
NO_HELP_MESSAGE = "NO HELP MESSAGE PROVIDED"
# Compatibility exports for final workflow CLI rendering helpers.
__all__ = ["cli_status", "log_status_tree", "status_lines", "workflow_command"]


def external_variables(workflow: Workflow) -> tuple[TaskVar[object], ...]:
    """Infer variables read before a visible workflow assignment.

    :param workflow: Workflow definition to analyze.
    :returns: External variables in first-use order.
    """
    assigned: set[str] = set()
    external: dict[str, TaskVar[object]] = {}

    def use(mapping: object | None, visible: set[str]) -> None:
        """Record unresolved direct variables from one argument mapping.

        :param mapping: Optional dataclass mapping.
        :param visible: Names assigned in the current scope.
        """
        for variable in mapping_variables(mapping):
            if variable.name not in visible:
                external.setdefault(variable.name, variable)

    def visit(task: TaskNode) -> None:
        """Analyze one task in parent-first depth-first order.

        :param task: Current task definition.
        """
        local = set(assigned)
        for context in task.context_tasks:
            use(context.args_mapping, local)
            local.update(item.name for item in mapping_variables(context.outputs_mapping))
        use(task.args_mapping, local)
        assigned.update(item.name for item in mapping_variables(task.outputs_mapping))
        for child in task.children:
            visit(child)

    visit(workflow.root_task)
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
    allowed = {item.name for item in variables}
    values, preset_masks = normalize_masked_mapping({} if preset is None else preset)
    unexpected = set(values) - allowed
    if unexpected:
        raise ValueError("workflow preset contains non-external variable")
    docs = tuple(
        ParameterDoc(
            item.name,
            item.value_type,
            True,
            item.description or NO_HELP_MESSAGE,
            masked=item.is_masked,
        )
        for item in variables
    )
    masked = preset_masks | {
        item.name for item in variables if item.is_masked and item.name in values
    }

    async def handler(context: CliContext) -> CliResult:
        """Execute the captured workflow through one CLI invocation.

        :param context: Current CLI invocation.
        :returns: Empty logger-only workflow result.
        :raises LclCliUsageError: If an override is not an external variable.
        """
        unknown = set(context.raw_params.overrides) - allowed
        if unknown:
            raise LclCliUsageError("workflow override targets non-external variable")
        result = await workflow.execute(
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
    )
