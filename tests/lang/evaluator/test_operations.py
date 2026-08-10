"""Unit tests mirroring :mod:`lclang.lang.evaluator.operations`."""

from dataclasses import dataclass

import pytest

from lclang import evaluate
from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.source import SourceSpan
from lclang.types import VarName


@dataclass(frozen=True)
class MatrixValue:
    """Provide a tiny trusted value implementing matrix multiplication."""

    value: int

    def __matmul__(self, other: object) -> int:
        """Combine two test matrix values."""
        assert isinstance(other, MatrixValue)
        return self.value * other.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("+value", 3),
        ("-value", -3),
        ("~value", -4),
        ("value + 2", 5),
        ("value - 2", 1),
        ("value * 2", 6),
        ("value / 2", 1.5),
        ("value // 2", 1),
        ("value % 2", 1),
        ("value ** 2", 9),
        ("value << 2", 12),
        ("value >> 1", 1),
        ("value & 1", 1),
        ("value ^ 1", 2),
        ("value | 4", 7),
    ],
)
async def test_arithmetic_and_bitwise_operators(source: str, expected: object) -> None:
    """Every ordinary numeric operator follows Python data-model semantics."""
    assert await evaluate(parse_expression(source), {"value": 3}) == expected


@pytest.mark.asyncio
async def test_matrix_multiplication_uses_value_protocol() -> None:
    """Matrix multiplication delegates to the trusted operand implementation."""
    values = {"left": MatrixValue(6), "right": MatrixValue(7)}
    assert await evaluate(parse_expression("left @ right"), values) == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a < b", True),
        ("a <= a", True),
        ("b > a", True),
        ("b >= b", True),
        ("a == a", True),
        ("a != b", True),
        ("a in items", True),
        ("b not in items", True),
        ("shared is alias", True),
        ("shared is not other", True),
    ],
)
async def test_comparison_operator_families(source: str, expected: bool) -> None:
    """Ordered, membership, equality, and identity comparisons are explicit."""
    shared = object()
    values = {
        "a": 1,
        "b": 2,
        "items": [1],
        "shared": shared,
        "alias": shared,
        "other": object(),
    }
    assert await evaluate(parse_expression(source), values) is expected


@pytest.mark.asyncio
async def test_comparison_chain_is_ordered_once_and_short_circuits() -> None:
    """A false link skips later operands and no middle value is resolved twice."""

    class RecordingResolver:
        def __init__(self) -> None:
            self.names: list[VarName] = []

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.names.append(name)
            return {"first": 3, "middle": 2}[str(name)]

    resolver = RecordingResolver()
    result = await evaluate(parse_expression("first < middle < skipped"), resolver)
    assert result is False
    assert resolver.names == [VarName("first"), VarName("middle")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, True), (2, False), (10, False), (-1, False), (11, False)],
)
async def test_descending_comparison_chain_uses_adjacent_values(
    value: int,
    expected: bool,
) -> None:
    """A descending chain compares both bounds to the shared middle value."""
    assert await evaluate(parse_expression("10 > x > 2"), {"x": value}) is expected


@pytest.mark.asyncio
async def test_operation_operands_are_awaited_left_to_right() -> None:
    """Deferred operands finish in source order before the operation runs."""
    events: list[str] = []

    async def deferred(name: str, value: int) -> int:
        events.append(name)
        return value

    values = {"left": deferred("left", 20), "right": deferred("right", 22)}
    assert await evaluate(parse_expression("left + right"), values) == 42
    assert events == ["left", "right"]


@pytest.mark.asyncio
async def test_data_model_failure_becomes_structured_cause() -> None:
    """Operator protocol failures retain their type beneath a public error."""
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("1 + 'x'"))
    assert isinstance(caught.value.__cause__, TypeError)
