"""Unit tests mirroring :mod:`lclang.lang.parser.pratt`."""

import pytest

from lclang.ast import LclBinary, LclConstant, LclName, LclUnary
from lclang.ast.operators import BinaryOperator, UnaryOperator
from lclang.errors import LclSyntaxError
from lclang.lang.parser import parse_expression
from lclang.version import LanguageVersion


def test_multiplication_binds_tighter_than_addition() -> None:
    """The Pratt ladder nests tighter binary operations on the right."""
    node = parse_expression("1 + 2 * 3")
    assert isinstance(node, LclBinary)
    assert node.operator is BinaryOperator.ADD
    assert isinstance(node.right, LclBinary)
    assert node.right.operator is BinaryOperator.MULTIPLY


def test_power_is_right_associative_with_python_unary_binding() -> None:
    """Power nesting and unary placement match the documented V1 contract."""
    power = parse_expression("2 ** 3 ** 2")
    assert isinstance(power, LclBinary)
    assert power.operator is BinaryOperator.POWER
    assert isinstance(power.right, LclBinary)
    left_unary = parse_expression("-2 ** 2")
    assert isinstance(left_unary, LclUnary)
    assert left_unary.operator is UnaryOperator.NEGATIVE
    assert isinstance(left_unary.operand, LclBinary)
    right_unary = parse_expression("2 ** -2")
    assert isinstance(right_unary, LclBinary)
    assert isinstance(right_unary.right, LclUnary)
    followed = parse_expression("2 ** 3 * 4")
    assert isinstance(followed, LclBinary)
    assert followed.operator is BinaryOperator.MULTIPLY


@pytest.mark.parametrize(
    ("source", "operator"),
    [
        ("1 | 2", BinaryOperator.BIT_OR),
        ("1 ^ 2", BinaryOperator.BIT_XOR),
        ("1 & 2", BinaryOperator.BIT_AND),
        ("1 << 2", BinaryOperator.LEFT_SHIFT),
        ("1 - 2", BinaryOperator.SUBTRACT),
        ("1 // 2", BinaryOperator.FLOOR_DIVIDE),
        ("1 @ 2", BinaryOperator.MATRIX_MULTIPLY),
    ],
)
def test_binary_operator_vocabulary(source: str, operator: BinaryOperator) -> None:
    """Every precedence family maps to the stable AST enum."""
    node = parse_expression(source)
    assert isinstance(node, LclBinary)
    assert node.operator is operator


def test_grouping_and_not_unary_parse() -> None:
    """Grouping changes reduction while ``not`` wraps its complete operand."""
    grouped = parse_expression("(1 + 2) * 3")
    assert isinstance(grouped, LclBinary)
    assert isinstance(grouped.left, LclBinary)
    negated = parse_expression("not name | 1")
    assert isinstance(negated, LclUnary)
    assert negated.operator is UnaryOperator.NOT
    assert isinstance(negated.operand, LclBinary)


def test_name_and_constant_are_public_parse_results() -> None:
    """The entry point accepts the simplest complete expressions."""
    assert isinstance(parse_expression("name"), LclName)
    assert isinstance(parse_expression("42"), LclConstant)


@pytest.mark.parametrize("source", ["", "1 2", "(1 + 2"])
def test_invalid_or_trailing_input_reports_syntax_error(source: str) -> None:
    """A public parse consumes exactly one supported complete expression."""
    with pytest.raises(LclSyntaxError):
        parse_expression(source)


def test_unsupported_runtime_version_is_rejected() -> None:
    """The public entry point validates versions even across untyped callers."""
    with pytest.raises(ValueError):
        parse_expression("1", version="2")  # type: ignore[arg-type]
    assert isinstance(parse_expression("1", version=LanguageVersion.V1), LclConstant)
