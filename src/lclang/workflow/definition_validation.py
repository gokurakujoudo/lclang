"""Validate workflow identifiers, callable signatures, and annotations."""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import cast, get_args, get_origin, get_type_hints

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.scopes import validate_qualified_name
from lclang.types import TaskID
from lclang.workflow.context import FailureCoveringContextTask, TaskContext
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.mappings.records import mapping_annotation
from lclang.workflow.variables import TaskVar


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_511)
def require_task_id(value: str) -> TaskID:
    """Return one unqualified valid LCL task identifier.

    :param value: Candidate identifier.
    :returns: Nominal workflow task identifier.
    :raises LclValidationError: If the value is qualified or invalid.
    """
    parts = validate_qualified_name(value)
    if len(parts) != 1:
        raise LclValidationError(
            "workflow task ID must be an unqualified LCL identifier",
            code=workflow_codes.E11_WORKFLOW_TASK_ID_MUST_BE_AN_UNQUALIFIED_LCL_IDENTIFIER,
        )
    return TaskID(value)


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_511)
def require_title(value: str, field: str) -> str:
    """Normalize one non-empty human-readable title.

    :param value: Candidate title.
    :param field: Diagnostic field label.
    :returns: Normalized title.
    :raises LclValidationError: If the value is not text.
    :raises LclValidationError: If normalized text is empty.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            f"{field} must be text", code=workflow_codes.E11_VALUE_MUST_BE_TEXT
        )
    result = " ".join(value.split())
    if not result:
        raise LclValidationError(
            f"{field} cannot be empty", code=workflow_codes.E11_VALUE_CANNOT_BE_EMPTY
        )
    return result


@guard_failure(LclValidationError, workflow_codes.NATIVE_511)
def validate_callable(value: object, *, coroutine: bool) -> None:
    """Validate the common three-parameter workflow callable shape.

    :param value: Candidate action or context factory.
    :param coroutine: Whether the callable itself must be an async function.
    :raises LclValidationError: If its runtime signature is incompatible.
    """
    if not callable(value):
        raise LclValidationError(
            "workflow callback must be callable", code=workflow_codes.CALLABLE_TYPE
        )
    if coroutine and not inspect.iscoroutinefunction(value):
        raise LclValidationError(
            "workflow action must be async", code=workflow_codes.ASYNC_ACTION_TYPE
        )
    try:
        parameters = tuple(inspect.signature(value).parameters.values())
    except (TypeError, ValueError) as error:
        raise LclValidationError(
            "workflow callback signature cannot be inspected",
            code=workflow_codes.SIGNATURE_UNAVAILABLE,
        ) from error
    if [item.name for item in parameters] != ["context", "args", "status_mgr"] or any(
        item.default is not inspect.Parameter.empty for item in parameters
    ):
        raise LclValidationError(
            "workflow callable must accept exactly context, args, status_mgr",
            code=workflow_codes.E11_WORKFLOW_CALLABLE_MUST_ACCEPT_EXACTLY_CONTEXT_ARGS_STATUS_MGR,
        )


@guard_failure(LclValidationError, workflow_codes.NATIVE_511)
def validate_annotations(
    value: object,
    args_mapping: object,
    outputs_mapping: object | None = None,
    *,
    context: bool = False,
) -> None:
    """Require exact public context, argument, and manager annotations.

    :param value: Callable whose annotations are resolved.
    :param args_mapping: Dataclass mapping selecting the argument type.
    :param outputs_mapping: Optional output mapping, including a whole-record variable.
    :param context: Whether the return annotation describes a context manager.
    :raises LclValidationError: If annotations cannot be resolved or do not match.
    """
    if isinstance(value, FailureCoveringContextTask):
        target = cast(FailureCoveringContextTask[object, object], value).acquire
    else:
        target = (
            value if inspect.isfunction(value) else getattr(value, "__call__")  # noqa: B004, B009
        )
    try:
        hints = get_type_hints(target)
    except Exception as error:
        raise LclValidationError(
            "workflow callable annotations cannot be resolved",
            code=workflow_codes.E11_WORKFLOW_CALLABLE_ANNOTATIONS_CANNOT_BE_RESOLVED,
        ) from error
    if (
        hints.get("context") is not TaskContext
        or hints.get("args") != mapping_annotation(args_mapping)
        or hints.get("status_mgr") is not ExecutionStatusManager
    ):
        raise LclValidationError(
            "workflow callable annotations do not match its mappings",
            code=workflow_codes.E11_WORKFLOW_CALLABLE_ANNOTATIONS_DO_NOT_MATCH_ITS_MAPPINGS,
        )
    if isinstance(outputs_mapping, TaskVar):
        result_type = hints.get("return")
        if context and get_origin(result_type) in {
            AsyncIterator,
            AsyncGenerator,
            AbstractAsyncContextManager,
        }:
            result_type = get_args(result_type)[0]
        if result_type != outputs_mapping.value_type:
            raise LclValidationError(
                "workflow output annotations do not match its mapping",
                code=workflow_codes.E11_WORKFLOW_OUTPUT_ANNOTATIONS_DO_NOT_MATCH_ITS_MAPPING,
            )
