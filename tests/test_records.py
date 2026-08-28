"""Behavioural tests for public immutable LCL record values."""

from collections.abc import Mapping
from typing import Any, cast

import pytest

import lclang


def test_record_snapshots_fields_and_prioritizes_field_attributes() -> None:
    """Construction detaches its shallow mapping while ordinary names remain fields."""
    nested: list[int] = [1]
    fields: dict[str, object] = {"a": 1, "fields": 2, "nested": nested}
    record = lclang.LclRecord(fields)
    fields["a"] = 9
    nested.append(2)

    assert record.a == 1
    assert record.fields == 2
    assert record.nested == [1, 2]
    assert repr(record) == "LclRecord(a=1, fields=2, nested=[1, 2])"
    assert not isinstance(record, Mapping)
    with pytest.raises(AttributeError):
        assert cast(Any, record)._fields is None
    with pytest.raises(TypeError):
        cast(Any, record)["a"]


def test_record_is_immutable_and_missing_fields_are_attributes_errors() -> None:
    """Python cannot add, replace, delete, or read an absent field."""
    record = lclang.LclRecord({"a": 1})
    with pytest.raises(AttributeError):
        cast(Any, record).a = 2
    with pytest.raises(AttributeError):
        cast(Any, record).other = 2
    with pytest.raises(AttributeError):
        del cast(Any, record).a
    with pytest.raises(AttributeError, match="missing"):
        assert cast(Any, record).missing is None


def test_record_equality_and_hash_ignore_declaration_order() -> None:
    """Names and values define record identity independently of source order."""
    first = lclang.LclRecord({"a": 1, "b": 2})
    second = lclang.LclRecord({"b": 2, "a": 1})

    assert first == second
    assert hash(first) == hash(second)
    assert first != {"a": 1, "b": 2}
    with pytest.raises(TypeError):
        hash(lclang.LclRecord({"items": []}))


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({}, ValueError),
        ({"__private": 1}, ValueError),
        ({"if": 1}, ValueError),
        ({"not valid": 1}, ValueError),
        ({1: "value"}, TypeError),
        ([], TypeError),
    ],
)
def test_record_constructor_rejects_fields_unavailable_to_lcl(
    fields: object,
    error: type[Exception],
) -> None:
    """Direct Python construction follows the record display's field grammar."""
    with pytest.raises(error):
        lclang.LclRecord(cast(Any, fields))
