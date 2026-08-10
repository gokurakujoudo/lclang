"""Unit tests mirroring :mod:`lclang.ast.primaries`."""

import pytest

from lclang.ast import LclConstant
from lclang.ast.primaries import LclAttribute, LclSafeAttribute, LclSlice, LclSubscript
from lclang.types import VarName


def test_attribute_subscript_and_slice_children_are_structural() -> None:
    """Names remain scalar metadata while expression operands are children."""
    value = LclConstant(value="value")
    lower = LclConstant(value=1)
    upper = LclConstant(value=3)
    step = LclConstant(value=2)
    slice_node = LclSlice(lower, upper, step)
    assert LclAttribute(value, VarName("name")).children() == (value,)
    assert LclSafeAttribute(value, VarName("name")).children() == (value,)
    assert LclSubscript(value, slice_node).children() == (value, slice_node)
    assert slice_node.children() == (lower, upper, step)
    assert LclSlice(None, upper, None).children() == (upper,)


@pytest.mark.parametrize("node", [LclAttribute, LclSafeAttribute])
def test_attribute_nodes_reject_empty_names(
    node: type[LclAttribute] | type[LclSafeAttribute],
) -> None:
    """Attribute syntax cannot carry an unusable member name."""
    with pytest.raises(ValueError):
        node(LclConstant(value=None), VarName(""))
