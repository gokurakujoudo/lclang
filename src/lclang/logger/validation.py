"""Shared validation and immutable declaration snapshots."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast


def mapping(value: object, path: str) -> dict[str, object]:
    """Copy a string-keyed mapping.

    :param value: Candidate mapping.
    :param path: Diagnostic configuration path.
    :returns: Detached dictionary.
    :raises TypeError: If the mapping or keys have incompatible types.
    """
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in cast(Mapping[object, object], value)
    ):
        raise TypeError(f"{path}: expected a string-keyed mapping")
    return dict(cast(Mapping[str, object], value))


def fields(value: object, allowed: set[str], path: str) -> dict[str, object]:
    """Reject unknown fields in a declaration.

    :param value: Candidate mapping.
    :param allowed: Unitless permitted field names from the configuration schema.
    :param path: Diagnostic configuration path.
    :returns: Detached declaration.
    :raises ValueError: If any field is unknown.
    """
    result = mapping(value, path)
    unknown = result.keys() - allowed
    if unknown:
        raise ValueError(f"{path}.{sorted(unknown)[0]}: unknown logger field")
    return result


def freeze(value: Mapping[str, object]) -> Mapping[str, object]:
    """Detach nested configuration containers without copying streams.

    :param value: Validated declaration.
    :returns: Read-only declaration retaining absent fields.
    """
    return MappingProxyType(
        {
            key: (
                freeze(mapping(cast(Mapping[object, object], item), key))
                if isinstance(item, Mapping)
                else (
                    tuple(cast(list[object] | tuple[object, ...], item))
                    if isinstance(item, (list, tuple))
                    else item
                )
            )
            for key, item in value.items()
        }
    )


def level(value: object, path: str) -> int:
    """Resolve standard level names or nonnegative integer levels.

    :param value: Level name or integer.
    :param path: Diagnostic configuration path.
    :returns: Numeric logging severity, in stdlib level units.
    :raises ValueError: If the level is invalid.
    """
    if isinstance(value, str):
        value = logging.getLevelNamesMapping().get(value.upper())
    if type(value) is not int or value < 0:
        raise ValueError(f"{path}: expected a logging level")
    return value


def boolean(value: object, path: str) -> bool:
    """Require an actual Boolean rather than coercing strings.

    :param value: Candidate flag.
    :param path: Diagnostic configuration path.
    :returns: Validated flag.
    :raises TypeError: If the value is not Boolean.
    """
    if not isinstance(value, bool):
        raise TypeError(f"{path}: expected bool (use LCL[False] in CLI overrides)")
    return value


def positive(value: object, path: str) -> float:
    """Require a finite positive duration.

    :param value: Seconds supplied as a number.
    :param path: Diagnostic configuration path.
    :returns: Positive seconds.
    :raises ValueError: If the duration is invalid.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: expected positive seconds")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{path}: expected positive seconds")
    return float(value)


def names(value: object, path: str) -> tuple[str, ...]:
    """Validate logger name collections.

    :param value: List or tuple of names.
    :param path: Diagnostic configuration path.
    :returns: Immutable logger names.
    :raises TypeError: If the container or a name is invalid.
    """
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item
        for item in cast(list[object] | tuple[object, ...], value)
    ):
        raise TypeError(f"{path}: expected nonempty logger names in a list or tuple")
    return tuple(cast(list[str] | tuple[str, ...], value))
