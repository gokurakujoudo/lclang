"""Workflow lifecycle and typed mapping log rendering."""

from __future__ import annotations

import logging
from dataclasses import MISSING, fields
from typing import Any, cast

from lclang.diagnostics import internal_render_value
from lclang.masking import MASKED_VALUE
from lclang.types import TaskID
from lclang.workflow.context import WorkflowExecutionContext
from lclang.workflow.models import ExecutionStatus
from lclang.workflow.variables import TaskVar


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


def typed_value(value: object, *, masked: bool = False) -> str:
    """Render a bounded typed mapping value while retaining masked types.

    :param value: Materialized field value.
    :param masked: Whether the payload must be hidden.
    :returns: Stable ``(type) value`` text.
    """
    if masked:
        return f"({type(value).__name__}) {MASKED_VALUE}"
    return internal_render_value(value)


def field_uses_default(item: Any, declared: object) -> bool:
    """Report whether a direct argument retains its fixed dataclass default.

    :param item: Dataclass field metadata.
    :param declared: Value retained by the definition mapping.
    :returns: Whether the fixed default remains selected.
    """
    return item.default is not MISSING and bool(declared == item.default)


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
    actual = cast(Any, value)
    declared = None if mapping is None else cast(Any, mapping)
    items = sorted(fields(actual), key=lambda item: item.name)
    width = max((len(item.name) for item in items), default=0)
    arrow = "->" if output else "<-"
    rows: list[str] = []
    for item in items:
        current = getattr(actual, item.name)
        marker = (
            mapping if isinstance(mapping, TaskVar)
            else None if declared is None else getattr(declared, item.name)
        )
        if isinstance(marker, TaskVar):
            target = f"[{marker.name}]"
            masked = (
                marker.is_masked or context.frame.is_masked(marker.name)
                or context.frame.is_masked(f"{marker.name}.{item.name}")
            )
        elif output:
            target = "unused"
            masked = False
        else:
            target = "default" if field_uses_default(item, marker) else "literal"
            masked = False
        rows.append(
            f"    {item.name.ljust(width)} {arrow} {target}: "
            f"{typed_value(current, masked=masked)}"
        )
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
