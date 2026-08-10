"""Scoped handles for individual workflow step nodes."""

from __future__ import annotations

from types import TracebackType
from typing import Literal, Self

from pylcl.workflow.finalization import (
    SharedExecutionState,
    ensure_unlocked,
    finalize_node,
)
from pylcl.workflow.models import (
    ExecutionStatus,
    ExecutionStatusTree,
    require_description,
    require_status,
)


class ExecutionStatusStep:
    """Update and finalize one manager-owned workflow step.

    :param current: Shared step node appended by its parent manager.
    :param state: Lock registry shared with the complete workflow tree.
    """

    __slots__ = ("current", "state")

    def __init__(
        self,
        current: ExecutionStatusTree,
        state: SharedExecutionState,
    ) -> None:
        """Create a handle over one shared step node.

        :param current: Shared step node appended by its parent manager.
        :param state: Lock registry shared with the complete workflow tree.
        :returns: ``None``.
        """
        self.current = current
        self.state = state

    def update(
        self,
        description: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> None:
        """Optionally replace the step description, status, or both.

        :param description: Replacement text, or ``None`` to preserve it.
        :param status: Replacement status, or ``None`` to preserve it.
        :returns: ``None``.
        :raises RuntimeError: If this step is finalized.
        :raises TypeError: If a replacement has an incompatible public type.

        .. note::
           Every supplied value is validated before either field changes.
        """
        ensure_unlocked(self.state, self.current)
        valid_description = (
            None if description is None else require_description(description)
        )
        valid_status = None if status is None else require_status(status)
        if valid_description is not None:
            self.current.task_description = valid_description
        if valid_status is not None:
            self.current.status = valid_status

    def __enter__(self) -> Self:
        """Enter this step scope while it remains editable.

        :returns: This exact step handle.
        :raises RuntimeError: If this step is finalized.
        """
        ensure_unlocked(self.state, self.current)
        return self

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Set the exit outcome, finalize, and never suppress exceptions.

        :param error_type: Raised exception type, or ``None`` on clean exit.
        :param error: Raised exception instance, or ``None`` on clean exit.
        :param traceback: Raised exception traceback, or ``None`` on clean exit.
        :returns: Always ``False`` so Python propagates any original exception.
        :raises RuntimeError: If this step was finalized inside its scope.
        """
        del error_type, traceback
        ensure_unlocked(self.state, self.current)
        if error is not None:
            self.current.status = ExecutionStatus.ERROR
            self.current.task_description = str(error)
        elif self.current.status is ExecutionStatus.RUNNING:
            self.current.status = ExecutionStatus.SUCCESS
        finalize_node(self.state, self.current)
        return False

