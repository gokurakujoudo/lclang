"""Mutable manager cursors and finalization for workflow status trees."""

from __future__ import annotations

from types import TracebackType
from typing import Literal, Self

from lclang.workflow.finalization import (
    SharedExecutionState,
    ensure_can_add,
    ensure_unlocked,
    finalize_node,
)
from lclang.workflow.models import (
    ExecutionStatus,
    ExecutionStatusTree,
    ExecutionTaskType,
    require_description,
    require_status,
)
from lclang.workflow.steps import ExecutionStatusStep


class ExecutionStatusManager:
    """Build and finalize one cursor within a shared execution-status tree.

    :param name: Non-empty name of the initial node.
    :param description: Initial human-readable detail.
    :param task_type: Initial composite-task or leaf-step category.
    :param status: Initial execution status.
    """

    __slots__ = ("current", "state")

    def __init__(
        self,
        name: str,
        description: str = "",
        task_type: ExecutionTaskType = ExecutionTaskType.TASK,
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> None:
        """Create a manager with one new root node.

        :param name: Non-empty name of the root node.
        :param description: Initial human-readable detail.
        :param task_type: Initial composite-task or leaf-step category.
        :param status: Initial execution status.
        :returns: ``None``.
        :raises TypeError: If a field has an incompatible public type.
        :raises ValueError: If *name* is empty.
        """
        self.current = ExecutionStatusTree(status, task_type, name, description)
        self.state = SharedExecutionState()

    def update(
        self,
        status: ExecutionStatus,
        description: str | None = None,
    ) -> None:
        """Replace the current status and optionally its description.

        :param status: New exact execution status.
        :param description: Replacement text, or ``None`` to preserve it.
        :returns: ``None``.
        :raises RuntimeError: If this manager's subtree is finalized.
        :raises TypeError: If a replacement has an incompatible type.
        """
        ensure_unlocked(self.state, self.current)
        valid_status = require_status(status)
        valid_description = None if description is None else require_description(description)
        self.current.status = valid_status
        if valid_description is not None:
            self.current.task_description = valid_description

    def add_step(
        self,
        name: str,
        description: str,
        status: ExecutionStatus = ExecutionStatus.RUNNING,
    ) -> ExecutionStatusStep:
        """Append one leaf step and return its scoped update handle.

        :param name: Non-empty step name.
        :param description: Step detail text.
        :param status: Initial status, defaulting to ``RUNNING``.
        :returns: Handle sharing and optionally scoping the appended step.
        :raises RuntimeError: If this manager's subtree is finalized.
        :raises TypeError: If an argument has an incompatible public type.
        :raises ValueError: If the current node is a step or *name* is empty.
        """
        ensure_can_add(self.state, self.current)
        child = ExecutionStatusTree(
            status,
            ExecutionTaskType.STEP,
            name,
            description,
        )
        self.current.sub_tasks.append(child)
        return ExecutionStatusStep(child, self.state)

    def add_sub_task(
        self,
        name: str,
        description: str,
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> ExecutionStatusManager:
        """Append one task and return a manager cursor for its shared subtree.

        :param name: Non-empty sub-task name.
        :param description: Sub-task detail text.
        :param status: Initial sub-task status.
        :returns: Manager sharing this tree and pointing at the new task.
        :raises RuntimeError: If this manager's subtree is finalized.
        :raises TypeError: If an argument has an incompatible public type.
        :raises ValueError: If the current node is a step or *name* is empty.
        """
        ensure_can_add(self.state, self.current)
        child = ExecutionStatusTree(status, ExecutionTaskType.TASK, name, description)
        self.current.sub_tasks.append(child)
        manager = ExecutionStatusManager(name, description, status=status)
        manager.current = child
        manager.state = self.state
        return manager

    def finalize(self) -> ExecutionStatusTree:
        """Finalize and lock the current subtree, returning its current node.

        :returns: The same tree node managed by this cursor.
        :raises RuntimeError: If this manager's subtree is already finalized.
        """
        ensure_unlocked(self.state, self.current)
        finalize_node(self.state, self.current)
        return self.current

    def __enter__(self) -> Self:
        """Enter a scoped manager and ensure it is still editable.

        :returns: This manager cursor.
        :raises RuntimeError: If this manager's subtree is already finalized.
        """
        ensure_unlocked(self.state, self.current)
        return self

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Record a scope error when present, finalize, and never suppress it.

        :param error_type: Raised exception type, or ``None`` on clean exit.
        :param error: Raised exception instance, or ``None`` on clean exit.
        :param traceback: Raised exception traceback, or ``None`` on clean exit.
        :returns: Always ``False`` so Python propagates any original exception.
        :raises RuntimeError: If this manager's subtree was finalized in the scope.
        """
        del error_type, traceback
        if error is not None:
            self.update(ExecutionStatus.ERROR, str(error))
        self.finalize()
        return False
