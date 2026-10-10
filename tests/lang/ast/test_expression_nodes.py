"""Unit tests mirroring :mod:`lclang.lang.ast.expression_nodes`."""

import pytest

from lclang.common.identifiers import VarName
from lclang.error import LclValidationError
from lclang.lang.ast import LclConstant, LclName
from lclang.lang.ast.expression_nodes import (
    LclBinary,
    LclBoolean,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclUnary,
)
from lclang.lang.ast.operator_nodes import (
    BinaryOperator,
    BooleanOperator,
    ComparisonOperator,
    UnaryOperator,
)


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
    with pytest.raises(LclValidationError):
        LclBoolean(BooleanOperator.OR, (value,))
    with pytest.raises(LclValidationError):
        LclCompare(value, (), ())
    with pytest.raises(LclValidationError):
        LclCompare(value, (ComparisonOperator.EQUAL,), ())
