"""Parent-first depth-first workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_type_hints

from lclang.runtime import Frame
from lclang.types import TaskID
from lclang.workflow.context import (
    TaskContext,
    WorkflowException,
    WorkflowExecutionContext,
)
from lclang.workflow.definitions import TaskNode
from lclang.workflow.logging import log_mapping, log_task_error
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.mappings import mapped_outputs, materialize_args
from lclang.workflow.mappings.records import record_type
from lclang.workflow.models import ExecutionStatus

# Statuses that stop declared workflow traversal.
# Unitless stop statuses below come from the workflow execution contract. The selected failure
# states prevent dependent child tasks from continuing after their prerequisites fail.
STOP_STATUSES = frozenset(
    {ExecutionStatus.FAILURE, ExecutionStatus.FAILURE_COVERED, ExecutionStatus.ERROR}
)


class WorkflowStatusStop(RuntimeError):
    """Carry one synthetic exception for an explicit stopping status."""


@dataclass(slots=True)
class WorkflowRunState:
    """Retain mutable values private to one workflow execution.

    :param context: Public execution context.
    :param task_args: Materialized action arguments.
    :param task_outputs: Returned action outputs.
    """

    context: WorkflowExecutionContext
    task_args: dict[TaskID, object]
    task_outputs: dict[TaskID, object]


def task_context_for(
    state: WorkflowRunState,
    task: TaskNode,
    frame: Frame,
    stack: tuple[TaskID, ...],
) -> TaskContext:
    """Build one action-visible context.

    :param state: Current execution state.
    :param task: Current task definition.
    :param frame: Current task-local Frame.
    :param stack: Root-to-current task path.
    :returns: Detached task context.
    """
    source = state.context
    return TaskContext(
        source.is_dryrun,
        source.as_of_date,
        source.verbose_mode,
        source.logger,
        frame,
        task,
        list(stack),
    )


def record_exception(
    state: WorkflowRunState,
    manager: ExecutionStatusManager,
    branch: tuple[TaskID, ...],
    error: Exception,
    *,
    preserve_status: bool = False,
) -> None:
    """Record one ordinary exception in status, logs, and the shared Frame.

    :param state: Current execution state.
    :param manager: Status manager owning the failure.
    :param branch: Root-to-originating-task identifier path.
    :param error: Original or synthetic exception.
    :param preserve_status: Whether an explicit status remains authoritative.
    """
    if not preserve_status:
        manager.update(ExecutionStatus.ERROR, str(error))
    error.add_note(f"workflow task {'.'.join(branch)}")
    log_task_error(state.context, branch, manager.current.status, error)
    state.context.frame.mixin(
        {"__exception__": WorkflowException(error, branch[-1])}
    )


def raise_for_status(
    state: WorkflowRunState,
    manager: ExecutionStatusManager,
    branch: tuple[TaskID, ...],
) -> None:
    """Raise and record a synthetic exception for a stopping status.

    :param state: Current execution state.
    :param manager: Manager whose current status is inspected.
    :param branch: Root-to-owning-task identifier path.
    :raises WorkflowStatusStop: If the current status stops traversal.
    """
    status = manager.current.status
    if status not in STOP_STATUSES:
        return
    error = WorkflowStatusStop(f"task '{branch[-1]}' ended with {status.value}")
    record_exception(state, manager, branch, error, preserve_status=True)
    raise error


def finalize_manager(manager: ExecutionStatusManager) -> None:
    """Finalize one manager with automatic clean success.

    :param manager: Editable status manager.
    """
    if manager.current.status is ExecutionStatus.RUNNING:
        manager.update(ExecutionStatus.SUCCESS)
    manager.finalize()


def add_skipped_task(parent: ExecutionStatusManager, task: TaskNode) -> None:
    """Materialize one complete unexecuted task branch as skipped.

    :param parent: Parent status manager.
    :param task: Unexecuted task definition.
    """
    manager = parent.add_sub_task(task.task_id, task.title, ExecutionStatus.SKIPPED)
    for context in task.context_tasks:
        manager.add_sub_task(
            context.task_id, context.title, ExecutionStatus.SKIPPED
        ).finalize()
    for child in task.children:
        add_skipped_task(manager, child)
    manager.finalize()


async def execute_action_and_children(
    state: WorkflowRunState,
    task: TaskNode,
    context: TaskContext,
    manager: ExecutionStatusManager,
    stack: tuple[TaskID, ...],
) -> bool:
    """Execute one action and its ordered children.

    :param state: Current workflow execution state.
    :param task: Current task definition.
    :param context: Current action context.
    :param manager: Current task status manager.
    :param stack: Root-to-current task path.
    :returns: Whether traversal may continue.
    :raises RuntimeError: If a validated action has lost its argument mapping.
    """
    if task.task_action is not None:
        if task.args_mapping is None:
            missing_mapping = RuntimeError(
                "validated action is missing its argument mapping"
            )
            record_exception(state, manager, stack, missing_mapping)
            raise missing_mapping
        try:
            args = await materialize_args(task.args_mapping, context.frame)
        except Exception as error:
            record_exception(state, manager, stack, error)
            raise
        state.task_args[task.task_id] = args
        log_mapping(state.context, stack, task.args_mapping, args, output=False)
        context._child_execution.action_active = True
        try:
            output = await task.task_action(context, args, manager)
        except Exception as error:
            record_exception(state, manager, stack, error)
            raise
        finally:
            context._child_execution.action_active = False
        return_type = get_type_hints(task.task_action).get("return")
        try:
            valid_output = type(output) is record_type(return_type)
        except TypeError:
            valid_output = False
        if not valid_output:
            wrong_output = TypeError(
                "workflow action must return its annotated dataclass"
            )
            record_exception(state, manager, stack, wrong_output)
            raise wrong_output
        state.task_outputs[task.task_id] = output
        try:
            published = await mapped_outputs(task.outputs_mapping, output, state.context.frame)
            if published:
                state.context.frame.mixin(published)
        except Exception as error:
            record_exception(state, manager, stack, error)
            raise
        raise_for_status(state, manager, stack)
    if context._child_execution.children_skipped:
        return True
    for index, child in enumerate(task.children):
        from lclang.workflow.runner import execute_task

        if not await execute_task(state, child, manager, (*stack, child.task_id)):
            for remaining in task.children[index + 1 :]:
                add_skipped_task(manager, remaining)
            return False
    return True
