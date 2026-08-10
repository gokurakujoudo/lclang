"""Public values for hierarchical workflow execution status."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Classify the current execution outcome of one workflow node."""

    # Work has not started.
    PENDING = "PENDING"
    # Work completed successfully.
    SUCCESS = "SUCCESS"
    # Work completed with an expected failure.
    FAILURE = "FAILURE"
    # Work stopped because of an unexpected error.
    ERROR = "ERROR"
    # Work was intentionally omitted.
    SKIPPED = "SKIPPED"
    # Work has started but has not completed.
    RUNNING = "RUNNING"


class ExecutionTaskType(StrEnum):
    """Distinguish composite tasks from leaf steps."""

    # A task may own nested tasks and steps.
    TASK = "TASK"
    # A step is always a leaf.
    STEP = "STEP"


@dataclass(slots=True)
class ExecutionStatusTree:
    """Store one workflow status node and its ordered children.

    :param status: Current execution status.
    :param task_type: Composite task or leaf-step category.
    :param task_name: Non-empty display name.
    :param task_description: Human-readable execution detail.
    :param sub_tasks: Ordered child nodes, permitted only for tasks.

    .. note::
       The child list is detached from the constructor input. Managers remain
       the supported mutation boundary after construction.
    """

    status: ExecutionStatus
    task_type: ExecutionTaskType
    task_name: str
    task_description: str = ""
    sub_tasks: list[ExecutionStatusTree] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate scalar fields and detach the child container.

        :returns: ``None``.
        :raises TypeError: If a field has an incompatible public type.
        :raises ValueError: If the name is empty or a step owns children.
        """
        require_status(self.status)
        require_task_type(self.task_type)
        require_task_name(self.task_name)
        require_description(self.task_description)
        if not isinstance(self.sub_tasks, list):
            raise TypeError("sub-tasks must be a list")
        if any(not isinstance(child, ExecutionStatusTree) for child in self.sub_tasks):
            raise TypeError("sub-tasks must contain ExecutionStatusTree values")
        if self.task_type is ExecutionTaskType.STEP and self.sub_tasks:
            raise ValueError("a step cannot contain sub-tasks")
        self.sub_tasks = list(self.sub_tasks)


def require_status(value: ExecutionStatus) -> ExecutionStatus:
    """Return one exact execution status or reject it.

    :param value: Candidate public status.
    :returns: The validated status.
    :raises TypeError: If *value* is not :class:`ExecutionStatus`.
    """
    if not isinstance(value, ExecutionStatus):
        raise TypeError("status must be ExecutionStatus")
    return value


def require_task_type(value: ExecutionTaskType) -> ExecutionTaskType:
    """Return one exact task type or reject it.

    :param value: Candidate public task category.
    :returns: The validated task type.
    :raises TypeError: If *value* is not :class:`ExecutionTaskType`.
    """
    if not isinstance(value, ExecutionTaskType):
        raise TypeError("task type must be ExecutionTaskType")
    return value


def require_task_name(value: str) -> str:
    """Return one non-empty textual task name.

    :param value: Candidate display name.
    :returns: The validated name without normalization.
    :raises TypeError: If *value* is not text.
    :raises ValueError: If *value* is empty.
    """
    if not isinstance(value, str):
        raise TypeError("task name must be text")
    if not value:
        raise ValueError("task name cannot be empty")
    return value


def require_description(value: str) -> str:
    """Return one textual task description.

    :param value: Candidate description, including empty text.
    :returns: The validated description without normalization.
    :raises TypeError: If *value* is not text.
    """
    if not isinstance(value, str):
        raise TypeError("task description must be text")
    return value
