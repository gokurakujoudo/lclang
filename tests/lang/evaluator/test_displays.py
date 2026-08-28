"""Unit tests mirroring :mod:`lclang.lang.evaluator.displays`."""

from collections.abc import Awaitable
from inspect import isawaitable
from typing import cast

import pytest

from lclang import LclRecord, evaluate
from lclang.ast import LclConstant, LclDict
from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.source import SourceSpan
from lclang.types import VarName


@pytest.mark.asyncio
async def test_sequence_displays_and_stars_preserve_order() -> None:
    """Tuple, list, and set displays evaluate and expand source-order values."""
    values = {"items": [2, 3]}
    assert await evaluate(parse_expression("(1, *items, 4)"), values) == (1, 2, 3, 4)
    assert await evaluate(parse_expression("[1, *items, 4]"), values) == [1, 2, 3, 4]
    assert await evaluate(parse_expression("{1, *items, 4}"), values) == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_dictionary_entries_expand_and_later_values_win() -> None:
    """Explicit and unpacked entries share deterministic update semantics."""
    values = {"base": {"a": 1, "b": 2}}
    result = await evaluate(parse_expression("{'a': 0, **base, 'b': 3}"), values)
    assert result == {"a": 1, "b": 3}


@pytest.mark.asyncio
async def test_record_fields_are_awaited_left_to_right_and_support_attributes() -> None:
    """Record construction is eager and both nested LCL and Python access work."""
    events: list[str] = []

    async def mark(name: str, value: object) -> object:
        events.append(name)
        return value

    result = await evaluate(
        parse_expression("{a=mark('a', 1), nested=mark('nested', {value=2})}"),
        {"mark": mark},
    )

    assert isinstance(result, LclRecord)
    assert result.a == 1
    assert result.nested.value == 2
    assert events == ["a", "nested"]
    assert await evaluate(parse_expression("{a=1, nested={value=2}}.nested.value")) == 2


@pytest.mark.asyncio
async def test_record_missing_attribute_uses_existing_safe_access_rules() -> None:
    """Safe access on a non-null record does not hide a missing field."""
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("{a=1}?.missing"))
    assert isinstance(caught.value.__cause__, AttributeError)


@pytest.mark.asyncio
async def test_display_evaluation_is_left_to_right() -> None:
    """Resolver access demonstrates strict element and entry ordering."""

    class RecordingResolver:
        def __init__(self) -> None:
            self.names: list[VarName] = []

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.names.append(name)
            return str(name)

    resolver = RecordingResolver()
    assert await evaluate(parse_expression("[first, second, third]"), resolver) == [
        "first",
        "second",
        "third",
    ]
    assert resolver.names == [VarName("first"), VarName("second"), VarName("third")]


@pytest.mark.asyncio
async def test_invalid_unpack_protocols_propagate_type_error() -> None:
    """Sequence and mapping protocol failures become structured causes."""
    with pytest.raises(LclEvaluationError) as sequence:
        await evaluate(parse_expression("[*value]"), {"value": 1})
    assert isinstance(sequence.value.__cause__, TypeError)
    with pytest.raises(LclEvaluationError) as mapping:
        await evaluate(parse_expression("{**value}"), {"value": 1})
    assert isinstance(mapping.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_dictionary_display_rejects_invalid_ast_entry() -> None:
    """A manually malformed dictionary entry is rejected instead of silently skipped."""
    malformed = LclDict((LclConstant(value="invalid"),))  # type: ignore[arg-type]
    with pytest.raises(LclEvaluationError, match="unsupported dictionary display entry") as caught:
        await evaluate(malformed)
    assert isinstance(caught.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_starred_map_awaits_lcl_function_results() -> None:
    """Materializing Python map over an LCL function never leaks coroutines."""
    result = await evaluate(
        parse_expression("[*map((x) -> x.lower(), ['A', 'B'])]"),
        {"map": map},
    )
    for value in cast(list[object], result):
        if isawaitable(value):
            await cast(Awaitable[object], value)
    assert result == ["a", "b"]
