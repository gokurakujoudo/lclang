"""Unit tests mirroring :mod:`lclang.lang.parser.primaries`."""

import pytest

from lclang.ast import (
    LclAttribute,
    LclCall,
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclPositionalArgument,
    LclSafeAttribute,
    LclSlice,
    LclStarArgument,
    LclSubscript,
    LclTuple,
)
from lclang.errors import LclSyntaxError
from lclang.lang.parser import parse_expression
from lclang.types import VarName


def test_attribute_and_safe_attribute_chain() -> None:
    """Postfix attribute forms reduce from left to right."""
    node = parse_expression("root.child?.leaf")
    assert isinstance(node, LclSafeAttribute)
    assert node.name == VarName("leaf")
    assert isinstance(node.value, LclAttribute)
    assert node.value.name == VarName("child")
    assert node.span.end.offset == len("root.child?.leaf")


def test_subscript_and_all_slice_shapes() -> None:
    """Index and independently optional slice bounds retain AST shape."""
    indexed = parse_expression("items[1 + 2]")
    assert isinstance(indexed, LclSubscript)
    assert not isinstance(indexed.index, LclSlice)
    full = parse_expression("items[1:stop:2]")
    assert isinstance(full, LclSubscript)
    assert isinstance(full.index, LclSlice)
    assert all(value is not None for value in (full.index.lower, full.index.upper, full.index.step))
    omitted = parse_expression("items[:stop:]")
    assert isinstance(omitted, LclSubscript)
    assert isinstance(omitted.index, LclSlice)
    assert omitted.index.lower is None
    assert omitted.index.upper is not None
    assert omitted.index.step is None
    two_part = parse_expression("items[1:stop]")
    assert isinstance(two_part, LclSubscript)
    assert isinstance(two_part.index, LclSlice)
    multiple = parse_expression("items[1, 2]")
    assert isinstance(multiple, LclSubscript)
    assert isinstance(multiple.index, LclTuple)
    trailing = parse_expression("items[1,]")
    triple = parse_expression("items[1, 2, 3]")
    assert isinstance(trailing, LclSubscript) and isinstance(trailing.index, LclTuple)
    assert isinstance(triple, LclSubscript) and isinstance(triple.index, LclTuple)


def test_call_preserves_explicit_argument_forms_and_trailing_comma() -> None:
    """Every call syntax form becomes its dedicated wrapper node."""
    node = parse_expression("function(1, *items, key=2, **options,)")
    assert isinstance(node, LclCall)
    assert tuple(type(argument) for argument in node.arguments) == (
        LclPositionalArgument,
        LclStarArgument,
        LclKeywordArgument,
        LclKeywordUnpackArgument,
    )
    keyword = node.arguments[2]
    assert isinstance(keyword, LclKeywordArgument)
    assert keyword.name == VarName("key")


def test_empty_call_and_mixed_primary_chain() -> None:
    """Each completed primary can receive another postfix operation."""
    empty = parse_expression("function()")
    assert isinstance(empty, LclCall)
    assert empty.arguments == ()
    single = parse_expression("function(1)")
    assert isinstance(single, LclCall)
    assert len(single.arguments) == 1
    chain = parse_expression("factory().items[0].name")
    assert isinstance(chain, LclAttribute)
    assert isinstance(chain.value, LclSubscript)


@pytest.mark.parametrize(
    "source",
    [
        "value.",
        "value?.",
        "value[",
        "value[]",
        "value[1::2:3]",
        "function(",
        "function(key=1, 2)",
        "function(**options, *items)",
        "function(key=1, key=2)",
        "function(1=2)",
        "function(value=)",
    ],
)
def test_invalid_primary_reports_syntax_error(source: str) -> None:
    """Malformed postfix syntax fails through one source-aware error type."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None
