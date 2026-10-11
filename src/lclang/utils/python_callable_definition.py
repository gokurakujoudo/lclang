"""Detached implementation locations for Python callables.

Defines ``PythonCallableDefinition``, ``describe_python_callable``, ``render_python_callable``.
"""

from dataclasses import dataclass
from functools import partial
from inspect import getattr_static
from types import BuiltinFunctionType, FunctionType, GetSetDescriptorType, MethodType
from typing import cast

from lclang.error.codes.e8_data_model_error_code import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor
from lclang.utils.value_representation import safe_repr


@guard_constructor(
    LclValidationError, DataModelErrorCode.E31_DIAGNOSTIC_RECORD_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class PythonCallableDefinition:
    """Retain code metadata without owning a callable, frame or source file.

    :param qualified_name: Actual code object's qualified implementation name.
    :param filename: Original code filename, including synthetic names.
    :param line: One-based first code line, without reading the source.
    :raises LclValidationError: If text is empty or the line is not a positive integer.
    """

    qualified_name: str
    filename: str
    line: int

    def __post_init__(self) -> None:
        """Validate detached location fields.

        :raises LclValidationError: If text or line metadata is invalid.
        """
        if not all(
            isinstance(value, str) and value for value in (self.qualified_name, self.filename)
        ):
            raise LclValidationError(
                "callable definition requires nonempty text",
                code=DataModelErrorCode.E31_CALLABLE_DEFINITION_TEXT,
            )
        if not isinstance(self.line, int) or isinstance(self.line, bool) or self.line < 1:
            raise LclValidationError(
                "callable definition line must be a positive integer",
                code=DataModelErrorCode.E31_CALLABLE_DEFINITION_LINE,
            )


def describe_python_callable(value: object) -> PythonCallableDefinition | None:
    """Locate the executed Python implementation using static metadata only.

    :param value: Already-resolved host value.
    :returns: Detached code location, or None for values without Python code.
    """
    visited: set[int] = set()
    while id(value) not in visited:
        visited.add(id(value))
        if isinstance(value, partial):
            value = partial.func.__get__(cast(partial[object], value))
        elif isinstance(value, MethodType):
            value = value.__func__
        elif isinstance(value, FunctionType):
            code = value.__code__
            if not code.co_qualname or not code.co_filename or code.co_firstlineno < 1:
                return None
            return PythonCallableDefinition(code.co_qualname, code.co_filename, code.co_firstlineno)
        elif callable(value):
            value = getattr_static(type(value), "__call__", None)
            if isinstance(value, (staticmethod, classmethod)):
                value = cast(object, value.__func__)
        else:
            break
    return None


def render_python_callable(value: object) -> str | None:
    """Summarize callable identity and its reliable implementation location.

    :param value: Already-resolved host value, unmasked by the caller.
    :returns: Protected callable text, or None when the value is not callable.
    """
    if isinstance(value, BuiltinFunctionType):
        return "Python callable " + safe_repr(value.__qualname__, renderer=str)
    if not callable(value):
        return None
    definition = describe_python_callable(value)
    if definition is not None:
        name = safe_repr(definition.qualified_name, renderer=str)
        filename = safe_repr(definition.filename, renderer=str, max_length=None)
        return f'Python function {name} ("{filename}":{definition.line})'
    descriptor = cast(GetSetDescriptorType, getattr_static(type, "__qualname__"))
    name = descriptor.__get__(type(value))
    return "Python callable " + safe_repr(name, renderer=str)
