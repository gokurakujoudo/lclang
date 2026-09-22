"""Public workflow execution context and failure values."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from lclang.logger import Logger
from lclang.runtime import Frame
from lclang.types import TaskID
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.models import ExecutionStatus, ExecutionStatusTree

if TYPE_CHECKING:
    from lclang.workflow.definitions import TaskNode


@dataclass(frozen=True, slots=True)
class WorkflowException:
    """Retain one execution failure and its originating task.

    :param exception: Original or synthetic ordinary exception.
    :param error_task: Task or context-task identifier owning the failure.
    """

    exception: Exception
    error_task: TaskID


@dataclass(frozen=True, slots=True)
class WorkflowExecutionContext:
    """Supply metadata and the shared Frame for one workflow execution.

    :param is_dryrun: Whether actions should avoid supported side effects.
    :param as_of_date: Effective business date.
    :param verbose_mode: Whether verbose diagnostics are active.
    :param logger: Standard-library execution logger.
    :param frame: Borrowed shared execution Frame.
    """

    is_dryrun: bool
    as_of_date: date
    verbose_mode: bool
    logger: logging.Logger | Logger
    frame: Frame


@dataclass(slots=True)
class TaskChildExecution:
    """Retain child traversal decisions for one task execution.

    :param action_active: Whether the action is currently running.
    :param children_skipped: Irreversible request to omit the entire child subtree.
    """

    action_active: bool = False
    children_skipped: bool = False


@dataclass(frozen=True, slots=True)
class TaskContext:
    """Expose services and identity for one executing task node.

    :param is_dryrun: Workflow dry-run signal.
    :param as_of_date: Effective business date.
    :param verbose_mode: Whether verbose diagnostics are active.
    :param logger: Execution logger.
    :param frame: Current task-local Frame.
    :param task_node: Current immutable task definition.
    :param task_id_stack: Root-to-current task identifier path.
    """

    is_dryrun: bool
    as_of_date: date
    verbose_mode: bool
    logger: logging.Logger | Logger
    frame: Frame
    task_node: TaskNode
    task_id_stack: list[TaskID]
    _child_execution: TaskChildExecution = field(
        default_factory=TaskChildExecution, init=False, repr=False, compare=False,
    )

    def log_event(
        self, event: str, *, level: int = logging.INFO, record: object | None = None,
        fields: Iterable[str] = (), masked_fields: Iterable[str] = (), **values: object,
    ) -> None:
        """Log a business event with explicit fields and pre-read masking.

        :param event: Application event name.
        :param level: Standard-library severity, defaulting to INFO.
        :param record: Optional dataclass instance; only selected fields are read.
        :param fields: Direct record fields in display order.
        :param masked_fields: Record or keyword names redacted before reading or formatting.
        :param values: Additional named values with no inferred identity-based masking.
        :raises TypeError: If an enabled event supplies a non-dataclass record.
        :raises ValueError: If selected fields are unknown, repeated, or conflict with values.
        :raises Exception: If an unmasked selected getter or logger raises.
        """
        from lclang.workflow.events import emit_event

        emit_event(self, event, level, record, fields, masked_fields, values)

    def skip_children(self) -> None:
        """Omit this task's child subtrees without creating status records.

        The request is idempotent and survives subsequent action or cleanup
        failures. It does not stop the action or prevent output publication.

        :raises RuntimeError: If called outside the action's active lifetime.
        """
        if not self._child_execution.action_active:
            raise RuntimeError("skip_children is only available during the task action")
        self._child_execution.children_skipped = True


@dataclass(frozen=True, slots=True)
class WorkflowExecutionResult:
    """Return workflow status, shared values, and materialized action values.

    :param execution_status: Finalized status tree.
    :param execution_frame: Borrowed shared execution Frame after publication.
    :param task_args: Successfully materialized action arguments by task ID.
    :param task_outputs: Successfully returned action outputs by task ID.
    """

    execution_status: ExecutionStatusTree
    execution_frame: Frame
    task_args: dict[TaskID, object]
    task_outputs: dict[TaskID, object]


class FailureCoveringContextTask[ArgsT, ResourceT]:
    """Template an async context that covers an inner ordinary exception."""

    async def acquire(
        self,
        context: TaskContext,
        args: ArgsT,
        status_mgr: ExecutionStatusManager,
    ) -> ResourceT:
        """Acquire and return the context resource.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context-task status manager.
        :returns: Acquired resource output.
        :raises NotImplementedError: Unless a subclass implements acquisition.
        """
        raise NotImplementedError

    async def handle_exception(
        self,
        context: TaskContext,
        args: ArgsT,
        status_mgr: ExecutionStatusManager,
        resource: ResourceT,
        exception: Exception,
    ) -> None:
        """Confirm one inner exception has been handled.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context-task status manager.
        :param resource: Acquired context resource.
        :param exception: Inner ordinary exception.
        :raises NotImplementedError: Unless a subclass implements handling.
        """
        raise NotImplementedError

    async def release(
        self,
        context: TaskContext,
        args: ArgsT,
        status_mgr: ExecutionStatusManager,
        resource: ResourceT,
    ) -> None:
        """Release a resource after clean or exceptional execution.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context-task status manager.
        :param resource: Acquired context resource.
        """

    @asynccontextmanager
    async def scope(
        self,
        context: TaskContext,
        args: ArgsT,
        status_mgr: ExecutionStatusManager,
    ) -> AsyncIterator[ResourceT]:
        """Run acquisition, optional covering, and release.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context-task status manager.
        :returns: Async iterator yielding the acquired resource.
        """
        resource = await self.acquire(context, args, status_mgr)
        covered = False
        try:
            yield resource
        except Exception as exception:
            await self.handle_exception(context, args, status_mgr, resource, exception)
            covered = True
        finally:
            await self.release(context, args, status_mgr, resource)
        if covered:
            status_mgr.update(ExecutionStatus.FAILURE_COVERED)

    def __call__(
        self,
        context: TaskContext,
        args: ArgsT,
        status_mgr: ExecutionStatusManager,
    ) -> AbstractAsyncContextManager[ResourceT]:
        """Return one fresh covering scope.

        :param context: Current task context.
        :param args: Materialized context arguments.
        :param status_mgr: Context-task status manager.
        :returns: Async context manager for this invocation.
        """
        return self.scope(context, args, status_mgr)
