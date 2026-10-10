"""Validation of explicit, possibly empty configuration namespaces.

Defines ``validate_namespace_names``, ``validate_namespace_conflicts``.
"""

from collections.abc import Iterable

from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.lang.common.binding_names import validate_qualified_name


@guard_failure(LclValidationError, DataModelErrorCode.E42_NAMESPACE_VALIDATION_NATIVE_FAILURE)
def validate_namespace_names(names: frozenset[str]) -> None:
    """Validate immutable explicit namespace metadata.

    :param names: Qualified namespace names, including empty namespaces.
    :raises LclValidationError: If the set or a namespace has an unsupported type.
    :raises LclValidationError: If a namespace is malformed or reserved.
    """
    if not isinstance(names, frozenset):
        raise LclValidationError(
            "namespace names must be a frozenset",
            code=DataModelErrorCode.E42_NAMESPACE_NAMES_MUST_BE_A_FROZENSET,
        )
    for name in names:
        validate_qualified_name(name)
        if name.startswith("__"):
            raise LclValidationError(
                "namespace name cannot be reserved",
                code=DataModelErrorCode.E42_NAMESPACE_NAME_CANNOT_BE_RESERVED,
            )


@guard_failure(LclValidationError, DataModelErrorCode.E42_NAMESPACE_VALIDATION_NATIVE_FAILURE)
def validate_namespace_conflicts(names: Iterable[str], real_names: Iterable[str]) -> None:
    """Reject ordinary values at or above an explicit namespace.

    :param names: Namespace reservations visible in one configuration or hierarchy.
    :param real_names: Ordinary effective binding names.
    :raises LclValidationError: If an ordinary binding occupies a namespace or its ancestor.
    """
    selected = set(real_names)
    for namespace in sorted(names):
        parts = namespace.split(".")
        for index in range(1, len(parts) + 1):
            name = ".".join(parts[:index])
            if name in selected:
                error = LclValidationError(
                    f"namespace {namespace!r} conflicts with binding {name!r}",
                    code=DataModelErrorCode.E42_NAMESPACE_BINDING_CONFLICT,
                )
                error.binding_names = (namespace, name)
                raise error
