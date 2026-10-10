"""Unit tests mirroring :mod:`lclang.stdlib.json_values`."""

from collections.abc import Iterator

import pytest

from lclang.error import LclStandardError, LclValidationError
from lclang.stdlib import json_decode, json_encode


def test_host_container_failure_retains_the_native_cause() -> None:
    """A host's iteration failure is distinct from detected JSON validation failures."""
    native = OSError("host iterator")

    class BrokenList(list[object]):
        def __iter__(self) -> Iterator[object]:
            raise native

    with pytest.raises(LclStandardError) as caught:
        json_encode(BrokenList([1]))
    assert caught.value.code == "LCL921890" and caught.value.__cause__ is native


def test_json_round_trip_is_compact_utf8_friendly_and_ordered() -> None:
    """Reviewed JSON preserves mapping order and emits Unicode directly."""
    encoded = json_encode({"message": "你好", "value": [1, True, None]})
    assert encoded == '{"message":"你好","value":[1,true,null]}'
    assert json_decode(encoded) == {"message": "你好", "value": [1, True, None]}


def test_json_helpers_reject_nonstandard_or_invalid_values() -> None:
    """NaN, unsupported objects, non-text input, and malformed JSON fail."""
    with pytest.raises(LclValidationError) as nonfinite:
        json_encode(float("nan"))
    assert nonfinite.value.code == "LCL921221"
    with pytest.raises(LclValidationError) as unsupported:
        json_encode(object())
    assert unsupported.value.code == "LCL921191"
    with pytest.raises(LclValidationError):
        json_decode(b"{}")  # type: ignore[arg-type]
    with pytest.raises(LclValidationError) as malformed:
        json_decode("{")
    assert malformed.value.code == "LCL921491"


@pytest.mark.parametrize("value", [float("inf"), {"value": [float("nan")]}, {float("inf"): 1}])
def test_nonfinite_values_share_one_specific_reason(value: object) -> None:
    """Scalar, nested, and key numbers share the same standard-JSON constraint."""
    with pytest.raises(LclValidationError) as caught:
        json_encode(value)
    assert caught.value.code == "LCL921221"


def test_json_cycles_and_key_types_have_distinct_codes() -> None:
    """Recursive containers and unsupported mapping keys are different input failures."""
    values: list[object] = []
    values.append(values)
    with pytest.raises(LclValidationError) as cycle:
        json_encode(values)
    assert cycle.value.code == "LCL921281"
    with pytest.raises(LclValidationError) as key:
        json_encode({(1, 2): "value"})
    assert key.value.code == "LCL921192"
    assert json_encode({1: (1.5, None)}) == '{"1":[1.5,null]}'
    assert json_encode({True: []}) == '{"true":[]}'
    assert json_encode({None: (1.5, None)}) == '{"null":[1.5,null]}'
    assert json_decode('{"value": 1.5}') == {"value": 1.5}


@pytest.mark.parametrize("source", ["NaN", "Infinity", '{"value": -Infinity}'])
def test_decoding_rejects_nonstandard_float_constants(source: str) -> None:
    """Decoded values obey the same finite-number contract as encoded inputs."""
    with pytest.raises(LclValidationError) as caught:
        json_decode(source)
    assert caught.value.code == "LCL921221"
