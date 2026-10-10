"""Explicit single-value wrappers without recursive conversion or validation.

Defines ``ValueBox``, ``CallableBox``, ``get_box_type``, ``box_value``, ``unbox_value``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, get_origin

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

# Unitless export names identify the supported concrete wrapper constructors.
__all__ = ["CallableBox", "ValueBox"]


@guard_constructor(LclValidationError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class ValueBox[T]:
    """Retain one value as a concrete type suitable for typed projections.

    :param value: Payload retained by reference, without runtime type validation.
    """

    value: T


@guard_constructor(LclValidationError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class CallableBox[**P, R]:
    """Retain and forward one callback with its parameter and result types.

    :param value: Callback retained by reference, without eager invocation.
    """

    value: Callable[P, R]

    @guard_failure(LclUtilityError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the stored callback once without awaiting or changing its result.

        :param args: Positional arguments forwarded unchanged.
        :param kwargs: Keyword arguments forwarded unchanged.
        :returns: The callback's original result, including an awaitable when returned.
        :raises Exception: If the callback raises.
        """
        return self.value(*args, **kwargs)


@guard_failure(LclUtilityError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
def get_box_type(annotation: object) -> type[ValueBox[Any]] | type[CallableBox[..., Any]] | None:
    """Identify an explicitly declared box, including named concrete subclasses.

    :param annotation: Runtime variable or projection annotation.
    :returns: Concrete wrapper class, or None for ordinary annotations.
    """
    origin = get_origin(annotation) or annotation
    if isinstance(origin, type) and issubclass(origin, (ValueBox, CallableBox)):
        return cast(type[ValueBox[Any]] | type[CallableBox[..., Any]], origin)
    return None


@guard_failure(LclUtilityError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
def box_value(value: object, annotation: object) -> object:
    """Wrap one explicit binding while preserving already wrapped instances.

    :param value: Original Frame value or selected record field.
    :param annotation: Declared binding annotation.
    :returns: Corresponding box or the original ordinary value.
    :raises LclValidationError: If an existing box has an incompatible concrete type.
    """
    original = value
    cls = get_box_type(annotation)
    if cls is None or isinstance(value, cls):
        return original
    if isinstance(value, (ValueBox, CallableBox)):
        raise LclValidationError(
            "workflow value has an incompatible box type",
            code=UtilityErrorCode.E21_WORKFLOW_VALUE_HAS_AN_INCOMPATIBLE_BOX_TYPE,
        )
    return cls(cast(Any, value))


@guard_failure(LclUtilityError, UtilityErrorCode.E21_VALUE_BOX_NATIVE_FAILURE)
def unbox_value(value: object, annotation: object) -> object:
    """Extract only an explicitly declared output binding's payload.

    :param value: Action or context output at one mapped binding.
    :param annotation: Declared output variable annotation.
    :returns: Box payload or the original ordinary value, without traversal.
    :raises LclValidationError: If a boxed output is not an instance of the declared box.
    """
    cls = get_box_type(annotation)
    if cls is None:
        return value
    if not isinstance(value, cls):
        raise LclValidationError(
            "workflow output must match its declared box type",
            code=UtilityErrorCode.E21_WORKFLOW_OUTPUT_MUST_MATCH_ITS_DECLARED_BOX_TYPE,
        )
    return cast(ValueBox[object] | CallableBox[..., object], value).value
