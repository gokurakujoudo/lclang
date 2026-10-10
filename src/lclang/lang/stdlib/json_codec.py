"""Reviewed strict standard JSON value encoding and decoding.

Defines ``json_encode``, ``json_decode``, ``validate_json_value``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import cast

from lclang.error import LclStandardError, StandardLibraryErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_failure


@guard_failure(LclStandardError, StandardLibraryErrorCode.E21_JSON_CODEC_NATIVE_FAILURE)
def json_encode(value: object) -> str:
    """Encode one value as compact UTF-8-friendly strict JSON text.

    :param value: Standard JSON-compatible Python value.
    :returns: Compact JSON preserving input mapping order.
    :raises LclValidationError: If *value* contains an unsupported object.
    :raises LclValidationError: If *value* contains NaN or infinity.
    :raises LclValidationError: If *value* contains cyclic containers or unsupported keys.

    .. note::
       Non-ASCII text is emitted directly and nonstandard floats are rejected.
    """
    validate_json_value(value, set())
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


@guard_failure(LclStandardError, StandardLibraryErrorCode.E21_JSON_CODEC_NATIVE_FAILURE)
def json_decode(value: str) -> object:
    """Decode strict JSON text into ordinary Python data values.

    :param value: JSON text to decode.
    :returns: Decoded scalar, list, or dictionary value.
    :raises LclValidationError: If *value* is not text.
    :raises LclValidationError: If *value* is not valid standard JSON.

    .. note::
       No object hooks, custom classes, or dynamic imports participate.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "JSON decode input must be a string",
            code=StandardLibraryErrorCode.E21_JSON_DECODE_INPUT_MUST_BE_A_STRING,
        )
    try:
        result: object = json.loads(value)
    except json.JSONDecodeError as error:
        raise wrap_failure(
            error, LclValidationError, StandardLibraryErrorCode.E21_JSON_SYNTAX
        ) from error
    validate_json_value(result, set())
    return result


def validate_json_value(value: object, active: set[int]) -> None:
    """Validate finite JSON values and detect cycles on the active container path.

    :param value: Scalar or nested container inspected before encoding or after decoding.
    :param active: Identities of containers on the current traversal path.
    :raises LclValidationError: If a number, key, value type, or container cycle is invalid.
    """
    if value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise LclValidationError(
                "JSON numbers must be finite", code=StandardLibraryErrorCode.E21_JSON_NONFINITE
            )
        return
    if not isinstance(value, (dict, list, tuple)):
        raise LclValidationError(
            "unsupported JSON value type", code=StandardLibraryErrorCode.E21_JSON_VALUE_TYPE
        )
    identity = id(cast(object, value))
    if identity in active:
        raise LclValidationError(
            "JSON containers cannot contain cycles", code=StandardLibraryErrorCode.E21_JSON_CYCLE
        )
    active.add(identity)
    try:
        if isinstance(value, dict):
            for key, item in cast(dict[object, object], value).items():
                if key is not None and not isinstance(key, (str, int, float)):
                    raise LclValidationError(
                        "unsupported JSON mapping key type",
                        code=StandardLibraryErrorCode.E21_JSON_KEY_TYPE,
                    )
                validate_json_value(key, active)
                validate_json_value(item, active)
        else:
            for item in cast(Sequence[object], value):
                validate_json_value(item, active)
    finally:
        active.remove(identity)
