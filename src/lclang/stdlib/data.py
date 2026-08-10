"""Reviewed shallow mapping helpers for the standard preset."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


def merge(*mappings: Mapping[object, object]) -> Mapping[object, object]:
    """Return a read-only shallow left-to-right mapping merge.

    :param mappings: Mapping values applied in argument order.
    :returns: Insertion-ordered read-only merged mapping.
    :raises TypeError: If any input does not implement Mapping.

    .. note::
       Later values replace collisions without recursively copying mapped data.
    """
    combined: dict[object, object] = {}
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            raise TypeError("data merge inputs must be mappings")
        combined.update(mapping)
    return MappingProxyType(combined)


def lookup(mapping: Mapping[object, object], key: object, default: object = None) -> object:
    """Return one mapped value or an explicit default.

    :param mapping: Mapping to query.
    :param key: Opaque lookup key.
    :param default: Value returned when *key* is absent.
    :returns: Present mapped value or *default*.
    :raises TypeError: If *mapping* does not implement Mapping.

    .. note::
       Present ``None`` values remain distinct from missing keys.
    """
    if not isinstance(mapping, Mapping):
        raise TypeError("data lookup input must be a mapping")
    return mapping.get(key, default)
