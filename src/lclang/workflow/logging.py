"""Workflow lifecycle and typed mapping log rendering."""

from __future__ import annotations

import logging

from lclang.types import TaskID
from lclang.workflow.context import WorkflowExecutionContext
from lclang.workflow.models import ExecutionStatus


def branch_text(branch: tuple[TaskID, ...]) -> str:
    """Join one root-to-current workflow identifier path.

    :param branch: Ordered task identifiers.
    :returns: Dot-connected branch text.
    """
    return ".".join(str(item) for item in branch)


def status_level(status: ExecutionStatus) -> int:
    """Select the logging level for one finalized workflow status.

    :param status: Final task or workflow status.
    :returns: Standard-library numeric logging level.
    """
    if status is ExecutionStatus.ERROR:
        return logging.ERROR
    if status in {ExecutionStatus.FAILURE, ExecutionStatus.FAILURE_COVERED}:
        return logging.WARNING
    return logging.INFO


def log_task_start(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    title: str,
) -> None:
    """Log one task or context-task start.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param title: Human-readable task title.
    """
    dryrun = " (dryrun)" if context.is_dryrun else ""
    context.logger.info("task start: [%s] %s%s", branch_text(branch), title, dryrun)


def log_task_error(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    status: ExecutionStatus,
    error: Exception,
) -> None:
    """Log one task failure with its original exception traceback.

    :param context: Shared workflow execution context.
    :param branch: Root-to-originating-task path.
    :param status: Current failure status.
    :param error: Original or synthetic ordinary exception.
    """
    context.logger.error(
        "task error: [%s] %s",
        branch_text(branch),
        status.value,
        exc_info=(type(error), error, error.__traceback__),
    )


def log_task_complete(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    status: ExecutionStatus,
) -> None:
    """Log one finalized task or context-task status.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param status: Finalized task status.
    """
    context.logger.log(
        status_level(status),
        "task complete: [%s] %s",
        branch_text(branch),
        status.value,
    )


def mapping_message(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    mapping: object | None,
    value: object,
    *,
    output: bool,
) -> str:
    """Render one aligned argument or output mapping record.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param mapping: Definition mapping, or ``None`` for wholly unused outputs.
    :param value: Materialized argument or output dataclass.
    :param output: Whether arrows describe output publication.
    :returns: Multi-line mapping message.
    """
    from lclang.workflow.mapping_logging import mapping_rows

    items = mapping_rows(mapping, value, context.frame, output=output)
    width = max((len(path) for path, _, _ in items), default=0)
    arrow = "->" if output else "<-"
    rows = [
        f"    {path.ljust(width)} {arrow} {target}: {rendered}"
        for path, target, rendered in items
    ]
    kind = "outputs" if output else "args"
    header = f"{kind} mapping: [{branch_text(branch)}] {type(value).__name__}"
    return header + "\n" + "\n".join(rows)


def log_mapping(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    mapping: object | None,
    value: object,
    *,
    output: bool,
) -> None:
    """Emit one verbose mapping record when requested.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param mapping: Definition mapping associated with the value.
    :param value: Materialized argument or output value.
    :param output: Whether this is an output mapping.
    """
    if not context.verbose_mode:
        return
    message = mapping_message(context, branch, mapping, value, output=output)
    context.logger.debug("%s", message)
