# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Context acquisition and unwinding for workflow execution."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import cast

from lclang.error import LclWorkflowError
from lclang.error.boundary import guard_async_failure
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.error.wrapping import wrap_failure
from lclang.types import TaskID
from lclang.workflow.context import (
    TaskContext,
)
from lclang.workflow.definitions import TaskNode
from lclang.workflow.execution import (
    WorkflowRunState,
    execute_action_and_children,
    finalize_manager,
    raise_for_status,
    record_exception,
)
from lclang.workflow.failures import combine_failures
from lclang.workflow.logging import (
    log_mapping,
    log_task_complete,
    log_task_start,
)
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.mappings import mapped_outputs, materialize_args
from lclang.workflow.models import ExecutionStatus


@guard_async_failure(LclWorkflowError, workflow_codes.NATIVE_532)
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
            error = record_exception(
                state, context_manager, branch, error, code=workflow_codes.CONTEXT_ENTER_FAILURE
            )
        finalize_manager(context_manager)
        log_task_complete(state.context, branch, context_manager.current.status)
        raise error
    incoming: BaseException | None = None
    completed = False
    try:
        try:
            updates = await mapped_outputs(definition.outputs_mapping, resource, task_context.frame)
        except Exception as error:
            mapping_failure = record_exception(
                state, context_manager, branch, error, code=workflow_codes.MAPPING_FAILURE
            )
            raise mapping_failure from mapping_failure.__cause__
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
        cleanup = (
            wrap_failure(error, LclWorkflowError, workflow_codes.CONTEXT_EXIT_FAILURE)
            if isinstance(error, Exception)
            else error
        )
        failure = combine_failures(incoming, cleanup)
        if isinstance(error, Exception):
            recorded = (
                failure
                if isinstance(failure, Exception)
                else wrap_failure(error, LclWorkflowError, workflow_codes.CONTEXT_EXIT_FAILURE)
            )
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
