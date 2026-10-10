"""Shared trailing-marker normalization for masked bindings.

Defines ``split_masked_name``, ``normalize_masked_mapping``, ``normalize_masked_names``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure

# Suffix declaring that one exact binding name is masked.
# Unitless markers follow the binding and presentation contract: ! is the trailing declaration
# syntax and *masked* is the stable replacement. Exact spellings preserve runtime-name
# normalization and consistent redaction.
MASK_SUFFIX = "!"
# Stable diagnostic replacement for masked payloads.
MASKED_VALUE = "*masked*"


@guard_failure(LclValidationError, DataModelErrorCode.E51_BINDING_MASK_NATIVE_FAILURE)
def split_masked_name(name: str) -> tuple[str, bool]:
    """Remove one optional trailing mask marker from a binding name.

    :param name: Raw binding spelling.
    :returns: Normalized name and whether it carried the marker.
    :raises LclValidationError: If *name* is not text.
    :raises LclValidationError: If the marker is empty, repeated, or separated by space.
    """
    if not isinstance(name, str):
        raise LclValidationError(
            "binding names must be strings",
            code=DataModelErrorCode.E51_BINDING_NAMES_MUST_BE_STRINGS,
        )
    if not name.endswith(MASK_SUFFIX):
        return name, False
    normalized = name[:-1]
    if not normalized or normalized.endswith(MASK_SUFFIX) or normalized[-1].isspace():
        raise LclValidationError(
            "invalid masked binding name", code=DataModelErrorCode.E51_INVALID_MASKED_BINDING_NAME
        )
    return normalized, True


@guard_failure(LclValidationError, DataModelErrorCode.E51_BINDING_MASK_NATIVE_FAILURE)
def normalize_masked_mapping[ValueT](
    values: Mapping[str, ValueT],
    masked_names: Iterable[str] = (),
) -> tuple[dict[str, ValueT], frozenset[str]]:
    """Normalize marked keys and combine explicit immutable mask metadata.

    :param values: String-keyed bindings to detach.
    :param masked_names: Already-normalized names to mark additionally.
    :returns: Detached normalized mapping and immutable exact-name mask set.
    :raises LclValidationError: If a mapping key or explicit name is not text.
    :raises LclValidationError: If normalized names collide or a marker is malformed.
    """
    normalized: dict[str, ValueT] = {}
    selected_masks: set[str] = set()
    for raw_name, value in values.items():
        name, masked = split_masked_name(raw_name)
        if name in normalized:
            raise LclValidationError(
                f"duplicate normalized binding name: {name}",
                code=DataModelErrorCode.E51_DUPLICATE_NORMALIZED_BINDING_NAME,
            )
        normalized[name] = value
        if masked:
            selected_masks.add(name)
    for name in normalize_masked_names(masked_names):
        if name not in normalized:
            raise LclValidationError(
                f"masked name has no binding: {name}",
                code=DataModelErrorCode.E51_MASKED_NAME_HAS_NO_BINDING,
            )
        selected_masks.add(name)
    return normalized, frozenset(selected_masks)


@guard_failure(LclValidationError, DataModelErrorCode.E51_BINDING_MASK_NATIVE_FAILURE)
def normalize_masked_names(masked_names: Iterable[str]) -> frozenset[str]:
    """Validate already-normalized exact-name mask metadata.

    :param masked_names: Names supplied separately from their bindings.
    :returns: Detached immutable name set.
    :raises LclValidationError: If a name is not text.
    :raises LclValidationError: If a name is empty or still carries a marker.
    """
    selected: set[str] = set()
    for raw_name in masked_names:
        name, marked = split_masked_name(raw_name)
        if not name or marked:
            raise LclValidationError(
                "masked-names metadata must use normalized names",
                code=DataModelErrorCode.E51_MASKED_NAMES_METADATA_MUST_USE_NORMALIZED_NAMES,
            )
        selected.add(name)
    return frozenset(selected)
