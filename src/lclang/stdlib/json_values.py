"""Reviewed strict standard JSON value encoding and decoding."""

from __future__ import annotations

import json


def json_encode(value: object) -> str:
    """Encode one value as compact UTF-8-friendly strict JSON text.

    :param value: Standard JSON-compatible Python value.
    :returns: Compact JSON preserving input mapping order.
    :raises TypeError: If *value* contains an unsupported object.
    :raises ValueError: If *value* contains NaN or infinity.

    .. note::
       Non-ASCII text is emitted directly and nonstandard floats are rejected.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def json_decode(value: str) -> object:
    """Decode strict JSON text into ordinary Python data values.

    :param value: JSON text to decode.
    :returns: Decoded scalar, list, or dictionary value.
    :raises TypeError: If *value* is not text.
    :raises ValueError: If *value* is not valid standard JSON.

    .. note::
       No object hooks, custom classes, or dynamic imports participate.
    """
    if not isinstance(value, str):
        raise TypeError("JSON decode input must be a string")
    result: object = json.loads(value)
    return result
