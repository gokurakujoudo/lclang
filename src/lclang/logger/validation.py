"""Shared validation and immutable declaration snapshots."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from lclang.error import LclLoggerError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.logging import Code as logging_codes


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def mapping(value: object, path: str) -> dict[str, object]:
    """Copy a string-keyed mapping.

    :param value: Candidate mapping.
    :param path: Diagnostic configuration path.
    :returns: Detached dictionary.
    :raises LclValidationError: If the mapping or keys have incompatible types.
    """
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in cast(Mapping[object, object], value)
    ):
        raise LclValidationError(
            f"{path}: expected a string-keyed mapping",
            code=logging_codes.E12_VALUE_EXPECTED_A_STRING_KEYED_MAPPING,
        )
    return dict(cast(Mapping[str, object], value))


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def fields(value: object, allowed: set[str], path: str) -> dict[str, object]:
    """Reject unknown fields in a declaration.

    :param value: Candidate mapping.
    :param allowed: Unitless permitted field names from the configuration schema.
    :param path: Diagnostic configuration path.
    :returns: Detached declaration.
    :raises LclValidationError: If any field is unknown.
    """
    result = mapping(value, path)
    unknown = result.keys() - allowed
    if unknown:
        raise LclValidationError(
            f"{path}.{sorted(unknown)[0]}: unknown logger field",
            code=logging_codes.E12_VALUE_VALUE_UNKNOWN_LOGGER_FIELD,
        )
    return result


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
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


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def level(value: object, path: str) -> int:
    """Resolve standard level names or nonnegative integer levels.

    :param value: Level name or integer.
    :param path: Diagnostic configuration path.
    :returns: Numeric logging severity, in stdlib level units.
    :raises LclValidationError: If the level is invalid.
    """
    if isinstance(value, str):
        value = logging.getLevelNamesMapping().get(value.upper())
    if type(value) is not int or value < 0:
        raise LclValidationError(
            f"{path}: expected a logging level",
            code=logging_codes.E12_VALUE_EXPECTED_A_LOGGING_LEVEL,
        )
    return value


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def boolean(value: object, path: str) -> bool:
    """Require an actual Boolean rather than coercing strings.

    :param value: Candidate flag.
    :param path: Diagnostic configuration path.
    :returns: Validated flag.
    :raises LclValidationError: If the value is not Boolean.
    """
    if not isinstance(value, bool):
        raise LclValidationError(
            f"{path}: expected bool (use LCL[False] in CLI overrides)",
            code=logging_codes.E12_VALUE_EXPECTED_BOOL_USE_LCL_FALSE_IN_CLI_OVERRIDES,
        )
    return value


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def positive(value: object, path: str) -> float:
    """Require a finite positive duration.

    :param value: Seconds supplied as a number.
    :param path: Diagnostic configuration path.
    :returns: Positive seconds.
    :raises LclValidationError: If the duration is invalid.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LclValidationError(
            f"{path}: expected positive seconds",
            code=logging_codes.E12_VALUE_EXPECTED_POSITIVE_SECONDS,
        )
    if not math.isfinite(value) or value <= 0:
        raise LclValidationError(
            f"{path}: expected positive seconds",
            code=logging_codes.E12_VALUE_EXPECTED_POSITIVE_SECONDS,
        )
    return float(value)


@guard_failure(LclLoggerError, logging_codes.NATIVE_612)
def names(value: object, path: str) -> tuple[str, ...]:
    """Validate logger name collections.

    :param value: List or tuple of names.
    :param path: Diagnostic configuration path.
    :returns: Immutable logger names.
    :raises LclValidationError: If the container or a name is invalid.
    """
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item
        for item in cast(list[object] | tuple[object, ...], value)
    ):
        raise LclValidationError(
            f"{path}: expected nonempty logger names in a list or tuple",
            code=logging_codes.E12_VALUE_EXPECTED_NONEMPTY_LOGGER_NAMES_IN_A_LIST_OR_TUPLE,
        )
    return tuple(cast(list[str] | tuple[str, ...], value))
