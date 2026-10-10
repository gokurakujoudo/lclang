"""Unit tests mirroring :mod:`lclang.lang.ast.operator_nodes`."""

from lclang.lang.ast.operator_nodes import (
    BinaryOperator,
    BooleanOperator,
    ComparisonOperator,
    UnaryOperator,
)


def test_operator_values_are_stable_source_spellings() -> None:
    """Parser and printer share exact V1 operator spellings through enums."""
    assert UnaryOperator.NOT.value == "not"
    assert BinaryOperator.POWER.value == "**"
    assert BooleanOperator.AND.value == "and"
    assert ComparisonOperator.NOT_IN.value == "not in"
    assert ComparisonOperator.IS_NOT.value == "is not"
