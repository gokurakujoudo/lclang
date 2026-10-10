# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Action-owned dynamic workflow calls with explicit Frame lifetime.

Defines ``close_call_frame``, ``execute_workflow_in_task``.
"""

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.diagnostic_rendering import render_failure
from lclang.error.exception_base import LclStateError, LclValidationError
from lclang.error.failure_aggregation import combine_failures
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_async_failure
from lclang.lang.runtime import Frame, Preset
from lclang.lang.runtime.module_frame_factory import define_frame
from lclang.workflow.call_status import attach_call_status, propagate_call_status
from lclang.workflow.execution_context import (
    TaskContext,
    WorkflowExecutionContext,
    WorkflowExecutionResult,
)
from lclang.workflow.execution_status import ExecutionStatus, ExecutionStatusTree, ExecutionTaskType
from lclang.workflow.status_manager import ExecutionStatusManager
from lclang.workflow.task_execution import finalize_manager
from lclang.workflow.task_logging import status_level
from lclang.workflow.workflow_definition import Workflow


@guard_async_failure(LclWorkflowError, WorkflowErrorCode.E41_WORKFLOW_CALL_NATIVE_FAILURE)
async def close_call_frame(frame: Frame) -> BaseException | None:
    """Wait for owned cleanup even when cancellation interrupts the waiting caller.

    :param frame: The call's exclusively owned execution Frame.
    :returns: Combined cancellation or cleanup failure, or None after clean closure.
    """
    closing = asyncio.create_task(frame.close())
    failure: BaseException | None = None
    while not closing.done():
        try:
            await asyncio.shield(closing)
        except asyncio.CancelledError as error:
            failure = combine_failures(failure, error, code=WorkflowErrorCode.E35_COMPOSITE_FAILURE)
        except BaseException:
            break
    try:
        closing.result()
    except BaseException as error:
        cleanup = (
            wrap_failure(error, LclWorkflowError, WorkflowErrorCode.E41_CALL_CLEANUP_FAILURE)
            if isinstance(error, Exception)
            else error
        )
        failure = combine_failures(failure, cleanup, code=WorkflowErrorCode.E35_COMPOSITE_FAILURE)
    return failure


@asynccontextmanager
async def execute_workflow_in_task(
    workflow: Workflow,
    context: TaskContext,
    parent: ExecutionStatusManager,
    *,
    name: str,
    preset: Mapping[str, object] | None,
) -> AsyncGenerator[WorkflowExecutionResult]:
    """Execute an isolated workflow before yielding its live borrowed-frame result.

    :param workflow: Reusable child definition, retaining normal mixin precedence.
    :param context: Active parent action's metadata and logger.
    :param parent: Editable parent action status manager.
    :param name: Unique display name among existing and declared child nodes.
    :param preset: Explicit shallow bindings, without implicit parent Frame inheritance.
    :returns: Async scope yielding native status, arguments, outputs and the owned Frame.
    :raises LclValidationError: If context, parent, preset or binding names have wrong types.
    :raises LclValidationError: If the name conflicts or parent cannot accept a child.
    :raises LclStateError: If outside an active action or the parent is finalized.
    :raises BaseException: On Frame setup/cleanup, body failure or cancellation.
       Ordinary child execution failures are represented by an ERROR result.
    """
    if not isinstance(context, TaskContext) or not isinstance(parent, ExecutionStatusManager):
        raise LclValidationError(
            "workflow calls require a task context and status manager",
            code=WorkflowErrorCode.E41_WORKFLOW_CALLS_REQUIRE_A_TASK_CONTEXT_AND_STATUS_MANAGER,
        )
    if not context._child_execution.action_active:
        raise LclStateError(
            "workflow calls are only available during the task action",
            code=WorkflowErrorCode.E41_WORKFLOW_CALLS_ARE_ONLY_AVAILABLE_DURING_THE_TASK_ACTION,
        )
    if preset is not None and not isinstance(preset, Mapping):
        raise LclValidationError(
            "workflow call preset must be a mapping",
            code=WorkflowErrorCode.E41_WORKFLOW_CALL_PRESET_MUST_BE_A_MAPPING,
        )
    values = {} if preset is None else dict(preset)
    Preset("workflow_call", values)
    reserved = {
        *(item.task_name for item in parent.current.sub_tasks),
        *(item.task_id for item in context.task_node.children),
        *(item.task_id for item in context.task_node.context_tasks),
    }
    if name in reserved:
        raise LclValidationError(
            "workflow call name conflicts with a child node",
            code=WorkflowErrorCode.E41_WORKFLOW_CALL_NAME_CONFLICTS_WITH_A_CHILD_NODE,
        )
    manager = parent.add_sub_task(name, workflow.title, ExecutionStatus.RUNNING)
    branch = ".".join((*context.task_id_stack, name))
    frame: Frame | None = None
    result: WorkflowExecutionResult | None = None
    pending: BaseException | None = None
    try:
        context.logger.info(
            "workflow call start: [%s] %s%s",
            branch,
            workflow.title,
            " (dryrun)" if context.is_dryrun else "",
        )
        frame = define_frame()
        frame.mixin(values)
        execution = WorkflowExecutionContext(
            context.is_dryrun,
            context.as_of_date,
            context.verbose_mode,
            context.logger,
            frame,
        )
        try:
            result = await workflow.execute(execution)
        except Exception as error:
            context.logger.error(
                "%s", render_failure(error, action=f"calling workflow {branch!r}"), exc_info=True
            )
            result = WorkflowExecutionResult(
                ExecutionStatusTree(
                    ExecutionStatus.ERROR, ExecutionTaskType.TASK, workflow.title, str(error)
                ),
                frame,
                {},
                {},
            )
        attach_call_status(manager, result.execution_status, workflow.root_task)
        propagate_call_status(parent, result.execution_status.status)
        yield result
    except BaseException as error:
        code = (
            WorkflowErrorCode.E41_CALL_SETUP_FAILURE
            if result is None
            else WorkflowErrorCode.E41_CALL_BODY_FAILURE
        )
        pending = (
            wrap_failure(error, LclWorkflowError, code) if isinstance(error, Exception) else error
        )
    finally:
        if frame is not None:
            cleanup = await close_call_frame(frame)
            if cleanup is not None:
                pending = combine_failures(
                    pending, cleanup, code=WorkflowErrorCode.E35_COMPOSITE_FAILURE
                )
                if result is not None:
                    result.execution_status.status = ExecutionStatus.ERROR
                    result.execution_status.task_description += " (Frame cleanup failed)"
        if pending is not None:
            manager.update(ExecutionStatus.ERROR, str(pending))
            propagate_call_status(parent, ExecutionStatus.ERROR)
            context.logger.error(
                "%s",
                render_failure(pending, action=f"calling workflow {branch!r}"),
                exc_info=(type(pending), pending, pending.__traceback__),
            )
        finalize_manager(manager)
        context.logger.log(
            status_level(manager.current.status),
            "workflow call complete: [%s] %s %s",
            branch,
            workflow.title,
            manager.current.status.value,
        )
    if pending is not None:
        raise pending
