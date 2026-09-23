"""Action-owned dynamic workflow calls with explicit Frame lifetime."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from lclang.api import define_frame
from lclang.runtime import Frame, Preset
from lclang.workflow.call_status import attach_call_status, propagate_call_status
from lclang.workflow.context import TaskContext, WorkflowExecutionContext, WorkflowExecutionResult
from lclang.workflow.definitions import Workflow
from lclang.workflow.execution import finalize_manager
from lclang.workflow.failures import combine_failures
from lclang.workflow.logging import status_level
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.models import ExecutionStatus, ExecutionStatusTree, ExecutionTaskType


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
            failure = combine_failures(failure, error)
        except BaseException:
            break
    try:
        closing.result()
    except BaseException as error:
        failure = combine_failures(failure, error)
    return failure


@asynccontextmanager
async def execute_workflow_in_task(
    workflow: Workflow, context: TaskContext, parent: ExecutionStatusManager, *,
    name: str, preset: Mapping[str, object] | None,
) -> AsyncIterator[WorkflowExecutionResult]:
    """Execute an isolated workflow before yielding its live borrowed-frame result.

    :param workflow: Reusable child definition, retaining normal mixin precedence.
    :param context: Active parent action's metadata and logger.
    :param parent: Editable parent action status manager.
    :param name: Unique display name among existing and declared child nodes.
    :param preset: Explicit shallow bindings, without implicit parent Frame inheritance.
    :returns: Async scope yielding native status, arguments, outputs and the owned Frame.
    :raises TypeError: If context, parent, preset or binding names have wrong types.
    :raises ValueError: If the name conflicts or parent cannot accept a child.
    :raises RuntimeError: If outside an active action or the parent is finalized.
    :raises BaseException: On Frame setup/cleanup, body failure or cancellation.
       Ordinary child execution failures are represented by an ERROR result.
    """
    if not isinstance(context, TaskContext) or not isinstance(parent, ExecutionStatusManager):
        raise TypeError("workflow calls require a task context and status manager")
    if not context._child_execution.action_active:
        raise RuntimeError("workflow calls are only available during the task action")
    if preset is not None and not isinstance(preset, Mapping):
        raise TypeError("workflow call preset must be a mapping")
    values = {} if preset is None else dict(preset)
    Preset("workflow_call", values)
    reserved = {
        *(item.task_name for item in parent.current.sub_tasks),
        *(item.task_id for item in context.task_node.children),
        *(item.task_id for item in context.task_node.context_tasks),
    }
    if name in reserved:
        raise ValueError("workflow call name conflicts with a child node")
    manager = parent.add_sub_task(name, workflow.title, ExecutionStatus.RUNNING)
    branch = ".".join((*context.task_id_stack, name))
    frame: Frame | None = None
    result: WorkflowExecutionResult | None = None
    pending: BaseException | None = None
    try:
        context.logger.info("workflow call start: [%s] %s%s", branch, workflow.title,
                            " (dryrun)" if context.is_dryrun else "")
        frame = define_frame()
        frame.mixin(values)
        execution = WorkflowExecutionContext(
            context.is_dryrun, context.as_of_date, context.verbose_mode, context.logger, frame,
        )
        try:
            result = await workflow.execute(execution)
        except Exception as error:
            context.logger.error("workflow call error: [%s]", branch, exc_info=True)
            result = WorkflowExecutionResult(
                ExecutionStatusTree(ExecutionStatus.ERROR, ExecutionTaskType.TASK,
                                    workflow.title, str(error)), frame, {}, {},
            )
        attach_call_status(manager, result.execution_status, workflow.root_task)
        propagate_call_status(parent, result.execution_status.status)
        yield result
    except BaseException as error:
        pending = error
    finally:
        if frame is not None:
            cleanup = await close_call_frame(frame)
            if cleanup is not None:
                pending = combine_failures(pending, cleanup)
                if result is not None:
                    result.execution_status.status = ExecutionStatus.ERROR
                    result.execution_status.task_description += " (Frame cleanup failed)"
        if pending is not None:
            manager.update(ExecutionStatus.ERROR, str(pending))
            propagate_call_status(parent, ExecutionStatus.ERROR)
            context.logger.error("workflow call error: [%s]", branch,
                                 exc_info=(type(pending), pending, pending.__traceback__))
        finalize_manager(manager)
        context.logger.log(status_level(manager.current.status),
                           "workflow call complete: [%s] %s %s",
                           branch, workflow.title, manager.current.status.value)
    if pending is not None:
        raise pending
