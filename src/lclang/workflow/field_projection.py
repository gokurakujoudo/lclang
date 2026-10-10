"""Typed read-only field paths rooted at workflow variables.

Defines ``TaskProjection``, ``project_field``, ``reference_name``.
"""

from dataclasses import dataclass

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.workflow.task_variable import TaskVar


@guard_constructor(LclValidationError, WorkflowErrorCode.E27_FIELD_PROJECTION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class TaskProjection[ValueT](TaskVar[ValueT]):
    """Retain a dataclass field path without creating a new binding.

    :param name: Root variable name, also used for dependency ownership.
    :param description: Root variable help text.
    :param is_masked: Root variable masking flag.
    :param value_type: Selected field annotation.
    :param root: Original variable declaration.
    :param path: Ordered dataclass field segments.
    """

    root: TaskVar[object]
    path: tuple[str, ...]


@guard_failure(LclWorkflowError, WorkflowErrorCode.E27_FIELD_PROJECTION_NATIVE_FAILURE)
def project_field[FieldT](
    source: TaskVar[object],
    name: str,
    field_type: type[FieldT],
) -> TaskProjection[FieldT]:
    """Validate and append one declared field to a reference.

    :param source: Root variable or preceding projection.
    :param name: Direct dataclass field name.
    :param field_type: Expected exact field annotation.
    :returns: New immutable field projection.
    :raises LclValidationError: If the field is not declared.
    :raises LclValidationError: If the source or field type is incompatible.
    """
    from lclang.workflow.mappings.record_annotation import record_annotations

    annotations = record_annotations(source.value_type)
    if name not in annotations:
        raise LclValidationError(
            f"unknown workflow field: {source.name}.{name}",
            code=WorkflowErrorCode.E27_UNKNOWN_WORKFLOW_FIELD,
        )
    if annotations[name] != field_type:
        raise LclValidationError(
            f"workflow field annotation mismatch: {source.name}.{name}",
            code=WorkflowErrorCode.E27_WORKFLOW_FIELD_ANNOTATION_MISMATCH,
        )
    root = source.root if isinstance(source, TaskProjection) else source
    path = (*source.path, name) if isinstance(source, TaskProjection) else (name,)
    return TaskProjection(
        root.name,
        root.description,
        root.is_masked,
        field_type,
        root,
        path,
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E27_FIELD_PROJECTION_NATIVE_FAILURE)
def reference_name(variable: TaskVar[object]) -> str:
    """Render a reference with its complete projected field path.

    :param variable: Root or projected workflow variable.
    :returns: Qualified diagnostic path, without a masking suffix.
    """
    return (
        ".".join((variable.name, *variable.path))
        if isinstance(
            variable,
            TaskProjection,
        )
        else variable.name
    )
