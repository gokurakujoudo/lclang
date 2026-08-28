"""Unit tests mirroring :mod:`lclang.ast.displays`."""

import pytest

from lclang.ast import LclConstant
from lclang.ast.displays import (
    LclDict,
    LclDictUnpack,
    LclKeyValue,
    LclList,
    LclRecordDisplay,
    LclRecordField,
    LclSet,
    LclStarred,
)
from lclang.types import VarName


def test_sequence_displays_and_unpacking_preserve_source_order() -> None:
    """List and set displays expose explicit starred values as child nodes."""
    first = LclConstant(value=1)
    second = LclConstant(value=2)
    starred = LclStarred(second)
    assert starred.children() == (second,)
    assert LclList((first, starred)).children() == (first, starred)
    assert LclSet((starred, first)).children() == (starred, first)


def test_dict_entries_distinguish_pairs_from_unpacking() -> None:
    """Dictionary shape is explicit rather than inferred from tuple length."""
    key = LclConstant(value="key")
    value = LclConstant(value=1)
    pair = LclKeyValue(key, value)
    unpack = LclDictUnpack(value)
    mapping = LclDict((pair, unpack))
    assert pair.children() == (key, value)
    assert unpack.children() == (value,)
    assert mapping.children() == (pair, unpack)


def test_record_fields_expose_only_value_children_in_source_order() -> None:
    """Record names remain metadata while field values drive traversal."""
    first = LclRecordField(VarName("a"), LclConstant(value=1))
    second = LclRecordField(VarName("b"), LclConstant(value=2))
    record = LclRecordDisplay((first, second))

    assert first.children() == (first.value,)
    assert record.children() == (first, second)


def test_record_ast_requires_names_and_at_least_one_field() -> None:
    """Manually constructed record trees retain their local invariants."""
    with pytest.raises(ValueError):
        LclRecordField(VarName(""), LclConstant(value=1))
    with pytest.raises(ValueError):
        LclRecordDisplay(())
