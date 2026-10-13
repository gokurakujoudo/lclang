"""Workflow lifecycle and typed mapping log rendering.

Defines ``branch_text``, ``status_level``, ``log_task_start``, ``log_task_error``,
``log_task_complete``, ``mapping_message``, ``log_mapping``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace

from lclang.error import LclWorkflowError, WorkflowErrorCode, WorkflowStatusStop
from lclang.error.diagnostic_rendering import render_failure
from lclang.error.failure_summary import describe_failure_reason
from lclang.error.operation_guard import guard_failure
from lclang.error.verbose_guard import guard_verbose_operation
from lclang.lang.runtime import Frame
from lclang.workflow.callback_timing import format_callback_times
from lclang.workflow.execution_context import WorkflowExecutionContext
from lclang.workflow.execution_status import ExecutionStatus
from lclang.workflow.log_identity import make_lifecycle_metadata
from lclang.workflow.task_id import TaskID


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def branch_text(branch: tuple[str, ...]) -> str:
    """Join one root-to-current workflow identifier path.

    :param branch: Ordered task identifiers.
    :returns: Dot-connected branch text.
    """
    return ".".join(str(item) for item in branch)


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
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


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
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
    path = branch_text((*context.log_task_prefix, *branch))
    context.logger.info(
        "Workflow task started: [%s] %s%s",
        path,
        title,
        dryrun,
        extra=make_lifecycle_metadata(path, context.is_dryrun),
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def log_task_error(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    status: ExecutionStatus,
    error: Exception,
) -> None:
    """Warn for isolated status stops or report real failures with their traceback.

    :param context: Shared workflow execution context.
    :param branch: Root-to-originating-task path.
    :param status: Current failure status.
    :param error: Original or synthetic ordinary exception.
    """
    path = branch_text((*context.log_task_prefix, *branch))
    extra = make_lifecycle_metadata(path, context.is_dryrun)
    if (
        isinstance(error, WorkflowStatusStop)
        and error.__cause__ is None
        and (error.__context__ is None or error.__suppress_context__)
    ):
        context.logger.warning(
            "Workflow task stopped: [%s] %s; reason: %s; skipped: remaining task traversal",
            path,
            status.value,
            describe_failure_reason(error),
            extra=extra,
        )
        return
    extra["lclang_failure_diagnostic"] = True
    context.logger.error(
        "Workflow task error: [%s] %s\n%s",
        path,
        status.value,
        render_failure(error, action=f"running workflow task {path!r}"),
        exc_info=(type(error), error, error.__traceback__),
        extra=extra,
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def log_task_complete(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    status: ExecutionStatus,
    times: Mapping[str, int] | None = None,
) -> None:
    """Log one finalized task or context-task status.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param status: Finalized task status.
    :param times: Callback body durations in nanoseconds, excluding unstarted phases.
    """
    path = branch_text((*context.log_task_prefix, *branch))
    context.logger.log(
        status_level(status),
        "Workflow task completed: [%s] %s%s",
        path,
        status.value,
        format_callback_times(times),
        extra=make_lifecycle_metadata(path, context.is_dryrun),
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
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
    from lclang.workflow.mappings.mapping_logging import mapping_rows

    items = mapping_rows(mapping, value, context.frame, output=output)
    width = max((len(path) for path, _, _ in items), default=0)
    arrow = "->" if output else "<-"
    rows = [
        f"    {path.ljust(width)} {arrow} {target}: {rendered}" for path, target, rendered in items
    ]
    kind = "outputs" if output else "args"
    path = branch_text((*context.log_task_prefix, *branch))
    header = f"{kind} mapping: [{path}] {type(value).__name__}"
    return header + "\n" + "\n".join(rows)


@guard_verbose_operation
def log_mapping(
    context: WorkflowExecutionContext,
    branch: tuple[TaskID, ...],
    mapping: object | None,
    value: object,
    *,
    output: bool,
    frame: Frame,
) -> None:
    """Emit one verbose mapping record when requested.

    :param context: Shared workflow execution context.
    :param branch: Root-to-current task path.
    :param mapping: Definition mapping associated with the value.
    :param value: Materialized argument or output value.
    :param output: Whether this is an output mapping.
    :param frame: Effective task Frame used for inherited masking.
    """
    if not context.verbose_mode:
        return
    effective = replace(context, frame=frame)
    message = mapping_message(effective, branch, mapping, value, output=output)
    context.logger.debug("%s", message)
