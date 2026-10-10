"""Public values for hierarchical workflow execution status."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.workflow import Code as workflow_codes


class ExecutionStatus(StrEnum):
    """Classify the current execution outcome of one workflow node."""

    # Work has not started.
    # Unitless status and node-kind labels below are public workflow serialization and display
    # values. Distinct spellings preserve pending, running, terminal and covered outcomes and
    # distinguish task ownership from detail steps.
    PENDING = "PENDING"
    # Work completed successfully.
    SUCCESS = "SUCCESS"
    # Work completed with an expected failure.
    FAILURE = "FAILURE"
    # Work failed but an enclosing context completed its recovery contract.
    FAILURE_COVERED = "FAILURE_COVERED"
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


@guard_constructor(LclValidationError, workflow_codes.NATIVE_552)
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
    sub_tasks: list[ExecutionStatusTree] = field(default_factory=list["ExecutionStatusTree"])

    @guard_failure(LclValidationError, workflow_codes.NATIVE_552)
    def __post_init__(self) -> None:
        """Validate scalar fields and detach the child container.

        :returns: ``None``.
        :raises LclValidationError: If a field has an incompatible public type.
        :raises LclValidationError: If the name is empty or a step owns children.
        """
        require_status(self.status)
        require_task_type(self.task_type)
        require_task_name(self.task_name)
        require_description(self.task_description)
        if not isinstance(self.sub_tasks, list):
            raise LclValidationError(
                "sub-tasks must be a list", code=workflow_codes.E52_SUB_TASKS_MUST_BE_A_LIST
            )
        if any(not isinstance(child, ExecutionStatusTree) for child in self.sub_tasks):
            raise LclValidationError(
                "sub-tasks must contain ExecutionStatusTree values",
                code=workflow_codes.E52_SUB_TASKS_MUST_CONTAIN_EXECUTIONSTATUSTREE_VALUES,
            )
        if self.task_type is ExecutionTaskType.STEP and self.sub_tasks:
            raise LclValidationError(
                "a step cannot contain sub-tasks",
                code=workflow_codes.E52_A_STEP_CANNOT_CONTAIN_SUB_TASKS,
            )
        self.sub_tasks = list(self.sub_tasks)


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_552)
def require_status(value: ExecutionStatus) -> ExecutionStatus:
    """Return one exact execution status or reject it.

    :param value: Candidate public status.
    :returns: The validated status.
    :raises LclValidationError: If *value* is not :class:`ExecutionStatus`.
    """
    if not isinstance(value, ExecutionStatus):
        raise LclValidationError(
            "status must be ExecutionStatus", code=workflow_codes.E52_STATUS_MUST_BE_EXECUTIONSTATUS
        )
    return value


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_552)
def require_task_type(value: ExecutionTaskType) -> ExecutionTaskType:
    """Return one exact task type or reject it.

    :param value: Candidate public task category.
    :returns: The validated task type.
    :raises LclValidationError: If *value* is not :class:`ExecutionTaskType`.
    """
    if not isinstance(value, ExecutionTaskType):
        raise LclValidationError(
            "task type must be ExecutionTaskType",
            code=workflow_codes.E52_TASK_TYPE_MUST_BE_EXECUTIONTASKTYPE,
        )
    return value


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_552)
def require_task_name(value: str) -> str:
    """Return one non-empty textual task name.

    :param value: Candidate display name.
    :returns: The validated name without normalization.
    :raises LclValidationError: If *value* is not text.
    :raises LclValidationError: If *value* is empty.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "task name must be text", code=workflow_codes.E52_TASK_NAME_MUST_BE_TEXT
        )
    if not value:
        raise LclValidationError(
            "task name cannot be empty", code=workflow_codes.E52_TASK_NAME_CANNOT_BE_EMPTY
        )
    return value


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_552)
def require_description(value: str) -> str:
    """Return one textual task description.

    :param value: Candidate description, including empty text.
    :returns: The validated description without normalization.
    :raises LclValidationError: If *value* is not text.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "task description must be text", code=workflow_codes.E52_TASK_NAME_MUST_BE_TEXT
        )
    return value
