"""Unit tests mirroring :mod:`pylcl.lang.evaluator.fstrings`."""

import pytest

from pylcl import evaluate
from pylcl.errors import LclEvaluationError
from pylcl.lang.parser import parse_expression


@pytest.mark.asyncio
async def test_text_and_values_join_in_source_order() -> None:
    """Literal and evaluated parts concatenate without separators."""
    node = parse_expression("f'hello {name}!'")
    assert await evaluate(node, {"name": "LCL"}) == "hello LCL!"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("conversion", "expected"),
    [("s", "é"), ("r", "'é'"), ("a", "'\\xe9'")],
)
async def test_explicit_conversions(conversion: str, expected: str) -> None:
    """The three V1 conversion flags run before final formatting."""
    node = parse_expression(f"f'{{value!{conversion}}}'")
    assert await evaluate(node, {"value": "é"}) == expected


@pytest.mark.asyncio
async def test_nested_format_spec_is_evaluated_semantically() -> None:
    """Replacement fields inside a format spec determine its final text."""
    node = parse_expression("f'{value:0{width}d}'")
    assert await evaluate(node, {"value": 42, "width": 5}) == "00042"


@pytest.mark.asyncio
async def test_debug_field_uses_canonical_label_and_python_defaults() -> None:
    """Debug output distinguishes repr default from explicit formatting."""
    plain = parse_expression("f'{value=}'")
    aligned = parse_expression("f'{value=:>4}'")
    assert await evaluate(plain, {"value": "x"}) == "value='x'"
    assert await evaluate(aligned, {"value": "x"}) == "value=   x"


@pytest.mark.asyncio
async def test_fields_evaluate_once_left_to_right_and_auto_await() -> None:
    """Async field calls preserve lexical order and execute only once."""
    values = iter((1, 2))
    events: list[int] = []

    async def next_value() -> int:
        value = next(values)
        events.append(value)
        return value

    node = parse_expression("f'{next_value()}{next_value()}'")
    assert await evaluate(node, {"next_value": next_value}) == "12"
    assert events == [1, 2]


@pytest.mark.asyncio
async def test_format_failure_is_source_aware_and_preserves_cause() -> None:
    """Application format errors cross the structured evaluation boundary."""

    class BrokenFormat:
        def __format__(self, spec: str) -> str:
            del spec
            raise ValueError("cannot format")

    node = parse_expression("f'{value:>4}'")
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(node, {"value": BrokenFormat()})
    assert caught.value.span == node.span
    assert isinstance(caught.value.__cause__, ValueError)
