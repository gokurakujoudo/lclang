"""Unit tests mirroring :mod:`pylcl.stdlib.json_values`."""

import pytest

from pylcl.stdlib import json_decode, json_encode


def test_json_round_trip_is_compact_utf8_friendly_and_ordered() -> None:
    """Reviewed JSON preserves mapping order and emits Unicode directly."""
    encoded = json_encode({"message": "你好", "value": [1, True, None]})
    assert encoded == '{"message":"你好","value":[1,true,null]}'
    assert json_decode(encoded) == {"message": "你好", "value": [1, True, None]}


def test_json_helpers_reject_nonstandard_or_invalid_values() -> None:
    """NaN, unsupported objects, non-text input, and malformed JSON fail."""
    with pytest.raises(ValueError):
        json_encode(float("nan"))
    with pytest.raises(TypeError):
        json_encode(object())
    with pytest.raises(TypeError):
        json_decode(b"{}")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        json_decode("{")
