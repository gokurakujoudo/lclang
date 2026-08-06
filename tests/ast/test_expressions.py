"""Unit tests mirroring :mod:`pylcl.ast.expressions`."""

import pytest

from pylcl.ast import LclConstant, LclName
from pylcl.ast.expressions import (
    LclBinary,
    LclBoolean,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclUnary,
)
from pylcl.ast.operators import (
    BinaryOperator,
    BooleanOperator,
    ComparisonOperator,
    UnaryOperator,
)
from pylcl.types import VarName


def test_expression_children_preserve_structural_source_order() -> None:
    """Ordinary operator nodes expose each operand exactly once."""
    left = LclName(identifier=VarName("left"))
    right = LclConstant(value=2)
    assert LclUnary(UnaryOperator.NEGATIVE, right).children() == (right,)
    assert LclBinary(left, BinaryOperator.ADD, right).children() == (left, right)
    assert LclCoalesce(left, right).children() == (left, right)


def test_boolean_comparison_and_conditional_children_are_deterministic() -> None:
    """Variable-length and conditional nodes retain declared source order."""
    first = LclConstant(value=1)
    second = LclConstant(value=2)
    third = LclConstant(value=3)
    boolean = LclBoolean(BooleanOperator.AND, (first, second, third))
    comparison = LclCompare(
        first,
        (ComparisonOperator.LESS, ComparisonOperator.LESS_EQUAL),
        (second, third),
    )
    conditional = LclConditional(first, second, third)
    assert boolean.children() == (first, second, third)
    assert comparison.children() == (first, second, third)
    assert conditional.children() == (first, second, third)


def test_variable_length_nodes_reject_invalid_cardinality() -> None:
    """Boolean and comparison invariants fail at construction boundaries."""
    value = LclConstant(value=1)
    with pytest.raises(ValueError):
        LclBoolean(BooleanOperator.OR, (value,))
    with pytest.raises(ValueError):
        LclCompare(value, (), ())
    with pytest.raises(ValueError):
        LclCompare(value, (ComparisonOperator.EQUAL,), ())
