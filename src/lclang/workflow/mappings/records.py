"""Dataclass annotation checks shared by whole-record workflow mappings."""

from dataclasses import is_dataclass
from inspect import signature
from typing import Any, get_origin

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.utils.boxes import get_box_type
from lclang.workflow.variables import TaskVar


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_524)
def can_construct_record(annotation: object) -> bool:
    """Inspect whether a definite record supplies every constructor field default.

    :param annotation: Concrete or generic record annotation, or any other type.
    :returns: Whether ordinary dataclass defaults can construct a missing record.
    """
    cls = get_origin(annotation) or annotation
    if not isinstance(cls, type) or not is_dataclass(cls) or get_box_type(annotation) is not None:
        return False
    try:
        signature(cls).bind()
    except TypeError, LclValidationError:
        return False
    return True


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_524)
def record_type(annotation: object) -> type[Any]:
    """Resolve a possibly parameterized dataclass annotation to its runtime class.

    :param annotation: Declared record annotation, retaining generic arguments elsewhere.
    :returns: Concrete dataclass class without runtime field-type validation.
    :raises LclValidationError: If the annotation does not identify a dataclass class.
    """
    origin = get_origin(annotation) or annotation
    if not isinstance(origin, type) or not is_dataclass(origin):
        raise LclValidationError(
            "workflow record type must be a dataclass",
            code=workflow_codes.E24_WORKFLOW_RECORD_TYPE_MUST_BE_A_DATACLASS,
        )
    return origin


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_524)
def mapping_annotation(mapping: object) -> object:
    """Return the exact annotation represented by a mapping.

    :param mapping: Dataclass instance or whole-record variable.
    :returns: Variable annotation or the concrete instance's declared generic type.
    """
    if isinstance(mapping, TaskVar):
        return mapping.value_type
    return getattr(mapping, "__orig_class__", type(mapping))
