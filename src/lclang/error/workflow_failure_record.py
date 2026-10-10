"""Workflow failure records with their originating task identifiers.

Defines ``WorkflowException``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lclang.error.codes.e5_workflow_error_code import WorkflowErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor

if TYPE_CHECKING:
    from lclang.workflow.task_id import TaskID


@guard_constructor(LclValidationError, WorkflowErrorCode.E33_WORKFLOW_CONTEXT_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class WorkflowException:
    """Retain one execution failure and its originating task.

    :param exception: Original or synthetic ordinary exception.
    :param error_task: Task or context-task identifier owning the failure.
    """

    exception: Exception
    error_task: TaskID
