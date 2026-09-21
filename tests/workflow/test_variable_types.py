"""Generic annotations retain the static type of variable quotes."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import assert_type

import pytest

import lclang.workflow as wf


@dataclass
class Record[T]:
    """One generic record field."""

    value: T


def test_parameterized_variables_keep_quote_types() -> None:
    """Strict mypy verifies real public subscriptions without casts."""
    items = wf.define_variable[list[str]]("items")
    lookup = wf.define_variable[Mapping[str, int]]("lookup")
    convert = wf.define_variable[Callable[[str], int]]("convert")
    optional = wf.define_variable[str | None]("optional")
    record = wf.define_variable[Record[int]]("record")
    assert_type(items.quote, list[str])
    assert_type(lookup.quote, Mapping[str, int])
    assert_type(convert.quote, Callable[[str], int])
    assert_type(optional.quote, str | None)
    assert_type(record.quote, Record[int])
    assert items.value_type == list[str]
    assert lookup.value_type == Mapping[str, int]
    assert convert.value_type == Callable[[str], int]
    assert optional.value_type == str | None
    assert record.value_type == Record[int]


def test_variable_subscription_is_required_and_none_is_a_type() -> None:
    """Unsubscribed construction has no inferred runtime type."""
    with pytest.raises(TypeError, match="subscription"):
        wf.define_variable("missing")
    null = wf.define_variable[None]("null")
    assert_type(null.quote, None)
    assert null.value_type is type(None)
