"""Context unwinding and task lifecycle for workflow execution."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, suppress
from typing import cast

from lclang.runtime import Frame, Module
from lclang.types import ModuleName, TaskID
from lclang.workflow.context import (
    TaskContext,
    WorkflowExecutionContext,
    WorkflowExecutionResult,
)
from lclang.workflow.definitions import TaskNode, Workflow
from lclang.workflow.execution import (
    STOP_STATUSES,
    WorkflowRunState,
    add_skipped_task,
    execute_action_and_children,
    finalize_manager,
    raise_for_status,
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
from lclang.workflow.mappings import mapped_outputs, materialize_args
from lclang.workflow.models import ExecutionStatus


async def execute_context_scope(
    state: WorkflowRunState,
    task: TaskNode,
    task_context: TaskContext,
    manager: ExecutionStatusManager,
    stack: tuple[TaskID, ...],
    index: int,
) -> bool:
    """Enter contexts recursively so ordinary async-exit suppression applies.

    :param state: Current execution state.
    :param task: Current task definition.
    :param task_context: Current action-visible context.
    :param manager: Current task status manager.
    :param stack: Root-to-current task path.
    :param index: Next context index.
    :returns: Whether traversal may continue.
    """
    if index == len(task.context_tasks):
        return await execute_action_and_children(state, task, task_context, manager, stack)
    definition = task.context_tasks[index]
    branch = (*stack, definition.task_id)
    context_manager = manager.add_sub_task(
        definition.task_id, definition.title, ExecutionStatus.RUNNING
    )
    log_task_start(state.context, branch, definition.title)
    try:
        args = await materialize_args(definition.args_mapping, task_context.frame)
        log_mapping(
            state.context,
            branch,
            definition.args_mapping,
            args,
            output=False,
            frame=task_context.frame,
        )
        scope = cast(
            AbstractAsyncContextManager[object],
            definition.task_context(task_context, args, context_manager),
        )
        resource = await scope.__aenter__()
    except BaseException as error:
        if isinstance(error, Exception):
            record_exception(state, context_manager, branch, error)
        finalize_manager(context_manager)
        log_task_complete(state.context, branch, context_manager.current.status)
        raise
    incoming: BaseException | None = None
    completed = False
    try:
        try:
            updates = await mapped_outputs(definition.outputs_mapping, resource, task_context.frame)
        except Exception as error:
            record_exception(state, context_manager, branch, error)
            raise
        if updates:
            task_context.frame.mixin(updates)
        raise_for_status(state, context_manager, branch)
        completed = await execute_context_scope(
            state, task, task_context, manager, stack, index + 1
        )
    except BaseException as error:
        incoming = error
    try:
        suppressed = await scope.__aexit__(
            None if incoming is None else type(incoming),
            incoming,
            None if incoming is None else incoming.__traceback__,
        )
    except BaseException as error:
        failure = combine_failures(incoming, error)
        if isinstance(error, Exception):
            recorded = failure if isinstance(failure, Exception) else error
            record_exception(state, context_manager, branch, recorded)
        finalize_manager(context_manager)
        log_task_complete(state.context, branch, context_manager.current.status)
        log_mapping(
            state.context,
            branch,
            definition.outputs_mapping,
            resource,
            output=True,
            frame=task_context.frame,
        )
        raise failure from failure.__cause__
    finalize_manager(context_manager)
    log_task_complete(state.context, branch, context_manager.current.status)
    log_mapping(
        state.context,
        branch,
        definition.outputs_mapping,
        resource,
        output=True,
        frame=task_context.frame,
    )
    if incoming is not None:
        if (
            isinstance(incoming, Exception)
            and suppressed
            and context_manager.current.status is ExecutionStatus.FAILURE_COVERED
        ):
            manager.update(ExecutionStatus.FAILURE_COVERED)
            return False
        raise incoming
    raise_for_status(state, context_manager, branch)
    return completed


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
            manager, task, omit_children=context._child_execution.children_skipped,
        )
    try:
        await frame.close()
    except BaseException as error:
        pending = combine_failures(pending, error)
        if isinstance(error, Exception):
            recorded = pending if isinstance(pending, Exception) else error
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


async def execute_workflow(
    workflow: Workflow,
    context: WorkflowExecutionContext,
) -> WorkflowExecutionResult:
    """Execute one validated workflow and capture ordinary failures.

    :param workflow: Reusable workflow definition.
    :param context: Execution metadata and borrowed Frame.
    :returns: Final status tree and materialized action values.
    :raises TypeError: If *context* has the wrong public type.
    """
    if not isinstance(context, WorkflowExecutionContext):
        raise TypeError("workflow execution context has the wrong type")
    if workflow.lcl_mixin:
        context.frame.mixin(dict(workflow.lcl_mixin))
    manager = ExecutionStatusManager(workflow.title, status=ExecutionStatus.RUNNING)
    state = WorkflowRunState(context, {}, {})
    with suppress(Exception):
        await execute_task(
            state, workflow.root_task, manager, (workflow.root_task.task_id,)
        )
    finalize_manager(manager)
    return WorkflowExecutionResult(
        manager.current, context.frame, dict(state.task_args), dict(state.task_outputs)
    )
