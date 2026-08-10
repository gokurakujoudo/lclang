"""Unit tests mirroring :mod:`lclang.lang.evaluator.logical`."""

import pytest

from lclang import evaluate
from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.source import SourceSpan
from lclang.types import VarName


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, True), (1, False), (None, True), ("value", False)],
)
async def test_logical_not_returns_boolean(value: object, expected: bool) -> None:
    """Logical negation uses the resolved operand's ordinary truth value."""
    assert await evaluate(parse_expression("not value"), {"value": value}) is expected


@pytest.mark.asyncio
async def test_boolean_operations_preserve_operand_values() -> None:
    """And/or return selected operands instead of coercing them to booleans."""
    values = {"truthy": "yes", "falsey": "", "final": 42}
    assert await evaluate(parse_expression("truthy and final"), values) == 42
    assert await evaluate(parse_expression("falsey and final"), values) == ""
    assert await evaluate(parse_expression("truthy or final"), values) == "yes"
    assert await evaluate(parse_expression("falsey or final"), values) == 42


@pytest.mark.asyncio
async def test_boolean_operations_skip_unselected_operands() -> None:
    """Resolver calls stop as soon as the Boolean result is determined."""

    class RecordingResolver:
        def __init__(self) -> None:
            self.names: list[VarName] = []

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.names.append(name)
            return {"first": False}[str(name)]

    resolver = RecordingResolver()
    assert await evaluate(parse_expression("first and skipped"), resolver) is False
    assert resolver.names == [VarName("first")]


@pytest.mark.asyncio
async def test_conditional_evaluates_condition_then_one_branch() -> None:
    """Runtime order starts at the condition despite source-order AST children."""

    class RecordingResolver:
        def __init__(self, condition: bool) -> None:
            self.condition = condition
            self.names: list[VarName] = []

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.names.append(name)
            return {
                "condition": self.condition,
                "when_true": "yes",
                "when_false": "no",
            }[str(name)]

    truthy = RecordingResolver(True)
    falsey = RecordingResolver(False)
    source = "when_true if condition else when_false"
    assert await evaluate(parse_expression(source), truthy) == "yes"
    assert truthy.names == [VarName("condition"), VarName("when_true")]
    assert await evaluate(parse_expression(source), falsey) == "no"
    assert falsey.names == [VarName("condition"), VarName("when_false")]


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [False, 0, "", (), []])
async def test_coalesce_retains_non_null_falsey_values(value: object) -> None:
    """Only None selects the coalescing fallback expression."""
    result = await evaluate(
        parse_expression("value ?? fallback"),
        {"value": value, "fallback": "fallback"},
    )
    assert result == value


@pytest.mark.asyncio
async def test_coalesce_evaluates_fallback_for_none() -> None:
    """A resolved null left value selects and resolves the right side."""
    values = {"value": None, "fallback": 42}
    assert await evaluate(parse_expression("value ?? fallback"), values) == 42


@pytest.mark.asyncio
async def test_truth_protocol_failure_becomes_structured_cause() -> None:
    """Truth-testing failures gain the logical node's source context."""
    failure = RuntimeError("truth failed")

    class BrokenTruth:
        def __bool__(self) -> bool:
            raise failure

    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("not value"), {"value": BrokenTruth()})
    assert caught.value.__cause__ is failure
