"""Selective dataclass flattening that preserves ordinary leaf references.

Defines ``flatten_to_dict``.
"""

from dataclasses import fields, is_dataclass
from typing import Any

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure

# Unitless export list identifies the supported conversion entry point.
__all__ = ["flatten_to_dict"]


@guard_failure(LclUtilityError, UtilityErrorCode.E51_DATACLASS_FLATTENING_NATIVE_FAILURE)
def flatten_to_dict(
    instance: object,
    prefix: str = "",
    nested: bool | set[str] = True,
) -> dict[str, object]:
    """Expand a dataclass into dotted keys without copying ordinary leaf values.

    :param instance: Dataclass instance whose direct fields are always expanded.
    :param prefix: Optional key prefix, separated from field names by one dot.
    :param nested: True recursively expands dataclass values; False stops after
       the root. A set selects relative record paths and their required ancestors.
    :returns: New dictionary retaining containers and unexpanded values by reference.
       Empty nested records remain leaves. Constructor factories are never called.
    :raises LclValidationError: If the root, prefix or expansion specification has a wrong type.
    :raises LclValidationError: If a selected path is malformed, absent or not a dataclass,
       or a recursively expanded path contains a cycle.
    :raises Exception: If reading a field raises.
    """
    if isinstance(instance, type) or not is_dataclass(instance):
        raise LclValidationError(
            "flatten_to_dict requires a dataclass instance",
            code=UtilityErrorCode.E51_FLATTEN_TO_DICT_REQUIRES_A_DATACLASS_INSTANCE,
        )
    if not isinstance(prefix, str):
        raise LclValidationError(
            "flattening prefix must be text",
            code=UtilityErrorCode.E51_FLATTENING_PREFIX_MUST_BE_TEXT,
        )
    if not isinstance(nested, (bool, set)):
        raise LclValidationError(
            "nested must be a bool or set of relative paths",
            code=UtilityErrorCode.E51_NESTED_MUST_BE_A_BOOL_OR_SET_OF_RELATIVE_PATHS,
        )
    selected: set[str] = set(nested) if isinstance(nested, set) else set()
    expand: set[str] = set()
    for path in selected:
        if not isinstance(path, str):
            raise LclValidationError(
                "selected paths must be strings",
                code=UtilityErrorCode.E51_FLATTENING_PREFIX_MUST_BE_TEXT,
            )
        parts = path.split(".")
        if not all(part.isidentifier() for part in parts):
            raise LclValidationError(
                "selected paths must be relative dotted field names",
                code=UtilityErrorCode.E51_SELECTED_PATHS_MUST_BE_RELATIVE_DOTTED_FIELD_NAMES,
            )
        expand.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
    output: dict[str, object] = {}
    visited: set[str] = set()

    def visit(record: Any, path: str, active: frozenset[int]) -> None:
        """Expand one selected record and retain each other value unchanged.

        :param record: Current dataclass instance.
        :param path: Current relative record path, empty at the root.
        :param active: Record identities on this traversal branch.
        :raises LclValidationError: If expansion encounters a cycle or non-record target.
        """
        if id(record) in active:
            raise LclValidationError(
                f"cyclic dataclass expansion at {path or '<root>'}",
                code=UtilityErrorCode.E51_CYCLIC_DATACLASS_EXPANSION_AT,
            )
        for item in fields(record):
            key = f"{path}.{item.name}" if path else item.name
            value = getattr(record, item.name)
            is_record = is_dataclass(value) and not isinstance(value, type)
            if key in expand and not is_record:
                raise LclValidationError(
                    f"selected path is not a dataclass: {key}",
                    code=UtilityErrorCode.E51_SELECTED_PATH_IS_NOT_A_DATACLASS,
                )
            if is_record and (nested is True or key in expand):
                visited.add(key)
                if fields(value):
                    visit(value, key, active | {id(record)})
                    continue
            output[f"{prefix}.{key}" if prefix else key] = value

    visit(instance, "", frozenset())
    if selected - visited:
        missing = ", ".join(sorted(selected - visited))
        raise LclValidationError(
            "unknown selected dataclass path: " + missing,
            code=UtilityErrorCode.E51_UNKNOWN_SELECTED_DATACLASS_PATH_MISSING,
        )
    return output
