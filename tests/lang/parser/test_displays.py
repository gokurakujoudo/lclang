"""Unit tests mirroring :mod:`lclang.lang.parser.displays`."""

import pytest

from lclang.ast import (
    LclDict,
    LclDictUnpack,
    LclKeyValue,
    LclList,
    LclRecordDisplay,
    LclSet,
    LclStarred,
    LclTuple,
)
from lclang.errors import LclSyntaxError
from lclang.lang.parser import parse_expression


def test_grouping_and_tuple_forms_are_distinct() -> None:
    """Only commas create tuples while grouping extends the enclosed span."""
    grouped = parse_expression("(1)")
    assert not isinstance(grouped, LclTuple)
    assert grouped.span.start.offset == 0
    assert grouped.span.end.offset == 3
    empty = parse_expression("()")
    singleton = parse_expression("(1,)")
    pair = parse_expression("(1, 2)")
    root = parse_expression("1, 2,")
    assert isinstance(empty, LclTuple) and empty.elements == ()
    assert isinstance(singleton, LclTuple) and len(singleton.elements) == 1
    assert isinstance(pair, LclTuple) and len(pair.elements) == 2
    assert isinstance(root, LclTuple) and len(root.elements) == 2


def test_list_display_preserves_starred_elements() -> None:
    """Empty, ordinary, unpacked, and trailing-comma list forms parse."""
    assert isinstance(parse_expression("[]"), LclList)
    node = parse_expression("[1, *items, 2,]")
    assert isinstance(node, LclList)
    assert len(node.elements) == 3
    assert isinstance(node.elements[1], LclStarred)


def test_set_display_is_distinct_from_empty_dict() -> None:
    """Non-empty brace elements choose set mode while empty braces choose dict."""
    empty = parse_expression("{}")
    node = parse_expression("{1, *items, 2}")
    assert isinstance(empty, LclDict) and empty.entries == ()
    assert isinstance(node, LclSet)
    assert isinstance(node.elements[1], LclStarred)


def test_dict_display_preserves_pair_and_unpack_entries() -> None:
    """Key/value and mapping-unpack forms stay structurally explicit."""
    node = parse_expression("{'key': 1, **defaults, other: 2,}")
    assert isinstance(node, LclDict)
    assert tuple(type(entry) for entry in node.entries) == (
        LclKeyValue,
        LclDictUnpack,
        LclKeyValue,
    )


def test_record_display_preserves_named_fields_and_trailing_comma() -> None:
    """An identifier followed by equals selects a non-empty record display."""
    node = parse_expression("{a=1, b=value,}")
    assert isinstance(node, LclRecordDisplay)
    assert tuple(str(field.name) for field in node.fields) == ("a", "b")
    assert node.span.start.offset == 0
    assert node.span.end.offset == len("{a=1, b=value,}")


@pytest.mark.parametrize(
    "source",
    [
        "[1",
        "[1,, 2]",
        "[*]",
        "[**mapping]",
        "{1: 2 3: 4}",
        "{1: 2, 3}",
        "{1, 2: 3}",
        "{**}",
        "{**mapping, *items}",
        "{1, **mapping}",
        "{1::2}",
        "{a=1, a=2}",
        "{__a=1}",
        "{a=1, b}",
        "{a=1, 'b': 2}",
        "{a=1, **other}",
        "{a=1 for a in values}",
        "{1, a=2}",
        "{'a': 1, b=2}",
    ],
)
def test_invalid_display_reports_syntax_error(source: str) -> None:
    """Incomplete, mixed-mode, and stray-delimiter forms are rejected."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None


def test_trailing_comma_set_and_non_trailing_root_tuple() -> None:
    """Both separator termination paths preserve their display type."""
    set_node = parse_expression("{1,}")
    tuple_node = parse_expression("1, 2")
    assert isinstance(set_node, LclSet)
    assert isinstance(tuple_node, LclTuple)
