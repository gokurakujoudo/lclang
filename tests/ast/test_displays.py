"""Unit tests mirroring :mod:`pylcl.ast.displays`."""

from pylcl.ast import LclConstant
from pylcl.ast.displays import (
    LclDict,
    LclDictUnpack,
    LclKeyValue,
    LclList,
    LclSet,
    LclStarred,
)


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
