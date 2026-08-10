"""Unit tests mirroring :mod:`lclang.lang.parser.logical`."""

import pytest

from lclang.ast import (
    LclBoolean,
    LclCall,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclList,
    LclSubscript,
    LclUnary,
)
from lclang.ast.operators import BooleanOperator, ComparisonOperator, UnaryOperator
from lclang.errors import LclSyntaxError
from lclang.lang.parser import parse_expression


def test_comparison_chain_preserves_all_operator_forms() -> None:
    """Two-word membership and identity operators join ordinary comparisons."""
    node = parse_expression("a < b <= c == d != e in f not in g is h is not i")
    assert isinstance(node, LclCompare)
    assert node.operators == (
        ComparisonOperator.LESS,
        ComparisonOperator.LESS_EQUAL,
        ComparisonOperator.EQUAL,
        ComparisonOperator.NOT_EQUAL,
        ComparisonOperator.IN,
        ComparisonOperator.NOT_IN,
        ComparisonOperator.IS,
        ComparisonOperator.IS_NOT,
    )
    assert len(node.comparators) == len(node.operators)


def test_not_comparison_and_boolean_precedence() -> None:
    """Comparison, not, and, then or nest from tightest to loosest."""
    node = parse_expression("not a == b and c and d or e")
    assert isinstance(node, LclBoolean)
    assert node.operator is BooleanOperator.OR
    conjunction = node.values[0]
    assert isinstance(conjunction, LclBoolean)
    assert conjunction.operator is BooleanOperator.AND
    assert len(conjunction.values) == 3
    negated = conjunction.values[0]
    assert isinstance(negated, LclUnary)
    assert negated.operator is UnaryOperator.NOT
    assert isinstance(negated.operand, LclCompare)


def test_null_coalescing_is_loose_and_right_associative() -> None:
    """Boolean expressions form operands and the fallback nests on the right."""
    node = parse_expression("a or b ?? c ?? d")
    assert isinstance(node, LclCoalesce)
    assert isinstance(node.left, LclBoolean)
    assert isinstance(node.right, LclCoalesce)


def test_conditional_is_loosest_and_false_branch_is_recursive() -> None:
    """Conditional values wrap coalescing and nest through the false branch."""
    node = parse_expression("a ?? b if condition else c if other else d")
    assert isinstance(node, LclConditional)
    assert isinstance(node.when_true, LclCoalesce)
    assert isinstance(node.when_false, LclConditional)


def test_logical_expressions_work_in_nested_parser_contexts() -> None:
    """Displays, calls, and subscriptions delegate to the full expression layer."""
    listed = parse_expression("[a and b]")
    called = parse_expression("function(a if c else b)")
    indexed = parse_expression("items[a ?? b]")
    assert isinstance(listed, LclList)
    assert isinstance(listed.elements[0], LclBoolean)
    assert isinstance(called, LclCall)
    assert isinstance(indexed, LclSubscript)
    assert isinstance(indexed.index, LclCoalesce)


@pytest.mark.parametrize(
    "source",
    [
        "a if b",
        "a if else b",
        "a ??",
        "a and",
        "a or or b",
        "a is not",
        "a not b",
        "a <",
    ],
)
def test_incomplete_logical_expression_reports_syntax_error(source: str) -> None:
    """Missing operands and incomplete compound operators are rejected."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None
