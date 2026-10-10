# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Context unwinding and task lifecycle for workflow execution."""

from __future__ import annotations

from contextlib import suppress

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_failure
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.error.wrapping import wrap_failure
from lclang.runtime import Frame, Module
from lclang.types import ModuleName, TaskID
from lclang.workflow.context import (
    WorkflowExecutionContext,
    WorkflowExecutionResult,
)
from lclang.workflow.context_execution import execute_context_scope
from lclang.workflow.defaults import execution_defaults
from lclang.workflow.definitions import TaskNode, Workflow
from lclang.workflow.execution import (
    STOP_STATUSES,
    WorkflowRunState,
    add_skipped_task,
    finalize_manager,
    record_exception,
    task_context_for,
)
from lclang.workflow.failures import combine_failures
from lclang.workflow.logging import (
    branch_text,
    log_mapping,
    log_task_complete,
    log_task_start,
)
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.models import ExecutionStatus


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_532)
def add_unexecuted_statuses(
    manager: ExecutionStatusManager,
    task: TaskNode,
    *,
    omit_children: bool = False,
) -> None:
    """Append every context and child not already represented in status.

    :param manager: Current task status manager.
    :param task: Current task definition.
    :param omit_children: Whether the action deliberately omitted child status records.
    """
    existing = {child.task_name for child in manager.current.sub_tasks}
    for definition in task.context_tasks:
        if definition.task_id not in existing:
            manager.add_sub_task(
                definition.task_id, definition.title, ExecutionStatus.SKIPPED
            ).finalize()
    if omit_children:
        return
    existing = {child.task_name for child in manager.current.sub_tasks}
    for child in task.children:
        if child.task_id not in existing:
            add_skipped_task(manager, child)


@guard_async_failure(LclWorkflowError, workflow_codes.NATIVE_532)
async def execute_task(
    state: WorkflowRunState,
    task: TaskNode,
    parent: ExecutionStatusManager,
    stack: tuple[TaskID, ...],
    parent_frame: Frame | None = None,
) -> bool:
    """Execute and finalize one declared task node.

    :param state: Current workflow execution state.
    :param task: Task definition to execute.
    :param parent: Parent status manager.
    :param stack: Root-to-current task path.
    :param parent_frame: Parent task lookup environment, or the shared Frame for the root.
    :returns: Whether traversal may continue.
    """
    manager = parent.add_sub_task(task.task_id, task.title, ExecutionStatus.RUNNING)
    log_task_start(state.context, stack, task.title)
    frame = (state.context.frame if parent_frame is None else parent_frame).derive(
        Module(ModuleName(str(task.task_id)), {}),
        {"__task_id_branch__": branch_text(stack)},
    )
    context = task_context_for(state, task, frame, stack)
    pending: BaseException | None = None
    completed = False
    try:
        completed = await execute_context_scope(state, task, context, manager, stack, 0)
    except BaseException as error:
        pending = error
    if pending is not None or not completed:
        add_unexecuted_statuses(
            manager,
            task,
            omit_children=context._child_execution.children_skipped,
        )
    try:
        await frame.close()
    except BaseException as error:
        cleanup = (
            wrap_failure(error, LclWorkflowError, workflow_codes.FRAME_CLOSE_FAILURE)
            if isinstance(error, Exception)
            else error
        )
        pending = combine_failures(pending, cleanup)
        if isinstance(error, Exception):
            recorded = (
                pending
                if isinstance(pending, Exception)
                else wrap_failure(error, LclWorkflowError, workflow_codes.FRAME_CLOSE_FAILURE)
            )
            record_exception(state, manager, stack, recorded)
    finalize_manager(manager)
    log_task_complete(state.context, stack, manager.current.status)
    output = state.task_outputs.get(task.task_id)
    if output is not None:
        log_mapping(
            state.context,
            stack,
            task.outputs_mapping,
            output,
            output=True,
            frame=frame,
        )
    if pending is not None:
        raise pending
    return completed and manager.current.status not in STOP_STATUSES


@guard_async_failure(LclWorkflowError, workflow_codes.NATIVE_532)
async def execute_workflow(
    workflow: Workflow,
    context: WorkflowExecutionContext,
) -> WorkflowExecutionResult:
    """Execute one validated workflow and capture ordinary failures.

    :param workflow: Reusable workflow definition.
    :param context: Execution metadata and borrowed Frame.
    :returns: Final status tree and materialized action values.
    :raises LclValidationError: If *context* has the wrong public type.
    """
    if not isinstance(context, WorkflowExecutionContext):
        raise LclValidationError(
            "workflow execution context has the wrong type",
            code=workflow_codes.E32_WORKFLOW_EXECUTION_CONTEXT_HAS_THE_WRONG_TYPE,
        )
    if workflow.lcl_mixin:
        context.frame.mixin(dict(workflow.lcl_mixin))
    manager = ExecutionStatusManager(workflow.title, status=ExecutionStatus.RUNNING)
    state = WorkflowRunState(context, {}, {})
    with suppress(Exception):
        async with execution_defaults(workflow, context.frame):
            await execute_task(state, workflow.root_task, manager, (workflow.root_task.task_id,))
    finalize_manager(manager)
    return WorkflowExecutionResult(
        manager.current, context.frame, dict(state.task_args), dict(state.task_outputs)
    )
