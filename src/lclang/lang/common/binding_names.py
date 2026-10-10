"""LCL binding-name validation.

Defines ``validate_qualified_name``, ``validate_binding_names``,
``validate_real_conflicts``.
"""

from __future__ import annotations

from collections.abc import Iterable

from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.lang.common.language_keywords import LCL_KEYWORDS

# Unitless reserved names protect language keywords and framework declaration markers.
LCL_RESERVED_NAMES = LCL_KEYWORDS | frozenset(
    {"True", "False", "None", "FRAME_PROXY", "NEED_OVERRIDE", "RUNTIME_OVERRIDE"}
)


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def validate_qualified_name(name: str) -> tuple[str, ...]:
    """Validate and split one LCL-qualified binding name.

    :param name: Candidate dot-separated name.
    :returns: Non-empty identifier segments.
    :raises LclValidationError: If *name* is not text.
    :raises LclValidationError: If a segment is not an LCL identifier.
    """
    if not isinstance(name, str):
        raise LclValidationError(
            "binding name must be a string",
            code=DataModelErrorCode.E41_BINDING_NAME_MUST_BE_A_STRING,
        )
    parts = tuple(name.split("."))
    if not parts or any(
        not part or not part.isidentifier() or part in LCL_RESERVED_NAMES for part in parts
    ):
        raise LclValidationError(
            f"invalid qualified binding name: {name}",
            code=DataModelErrorCode.E41_INVALID_QUALIFIED_BINDING_NAME,
        )
    return parts


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def validate_binding_names(names: Iterable[str]) -> None:
    """Validate dotted names while retaining legacy flat host keys.

    :param names: Binding names to inspect.
    :raises LclValidationError: If a dotted name is malformed.
    """
    for name in names:
        if "." in name:
            validate_qualified_name(name)


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def validate_real_conflicts(names: Iterable[str]) -> None:
    """Reject strict ancestor relationships among real binding names.

    :param names: Effective real names; exact duplicates are allowed.
    :raises LclValidationError: If one real name is a strict dotted prefix of another.
    """
    unique = tuple(dict.fromkeys(names))
    selected = set(unique)
    for name in unique:
        parts = name.split(".")
        for index in range(1, len(parts)):
            ancestor = ".".join(parts[:index])
            if ancestor in selected:
                error = LclValidationError(
                    f"scoped binding conflict between {ancestor!r} and {name!r}",
                    code=DataModelErrorCode.E41_SCOPED_BINDING_PREFIX_CONFLICT,
                )
                error.binding_names = (ancestor, name)
                raise error
