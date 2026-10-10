"""Reviewed shallow mapping helpers for the standard preset."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from lclang.error import LclStandardError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.standard import Code as standard_codes


@guard_failure(LclStandardError, standard_codes.NATIVE_951)
def merge(*mappings: Mapping[object, object]) -> Mapping[object, object]:
    """Return a read-only shallow left-to-right mapping merge.

    :param mappings: Mapping values applied in argument order.
    :returns: Insertion-ordered read-only merged mapping.
    :raises LclValidationError: If any input does not implement Mapping.

    .. note::
       Later values replace collisions without recursively copying mapped data.
    """
    combined: dict[object, object] = {}
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            raise LclValidationError(
                "data merge inputs must be mappings",
                code=standard_codes.E51_DATA_MERGE_INPUTS_MUST_BE_MAPPINGS,
            )
        combined.update(mapping)
    return MappingProxyType(combined)


@guard_failure(LclStandardError, standard_codes.NATIVE_951)
def lookup(mapping: Mapping[object, object], key: object, default: object = None) -> object:
    """Return one mapped value or an explicit default.

    :param mapping: Mapping to query.
    :param key: Opaque lookup key.
    :param default: Value returned when *key* is absent.
    :returns: Present mapped value or *default*.
    :raises LclValidationError: If *mapping* does not implement Mapping.

    .. note::
       Present ``None`` values remain distinct from missing keys.
    """
    if not isinstance(mapping, Mapping):
        raise LclValidationError(
            "data lookup input must be a mapping",
            code=standard_codes.E51_DATA_LOOKUP_INPUT_MUST_BE_A_MAPPING,
        )
    return mapping.get(key, default)
