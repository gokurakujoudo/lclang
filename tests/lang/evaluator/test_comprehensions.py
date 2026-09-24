"""Unit tests mirroring :mod:`lclang.lang.evaluator.comprehensions`."""

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Iterator
from inspect import isawaitable
from typing import cast

import pytest

from lclang import evaluate
from lclang.ast import LclConstant, LclDictComprehension
from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression


class AsyncValues:
    """Provide an async-only source for comprehension tests."""

    def __init__(self, values: list[int]) -> None:
        """Store values for later asynchronous iteration."""
        self.values = values

    async def __aiter__(self) -> AsyncIterator[int]:
        """Yield stored values asynchronously."""
        for value in self.values:
            yield value


@pytest.mark.asyncio
async def test_nested_list_comprehension_has_isolated_targets() -> None:
    """Nested clauses and conditions see locals without changing caller values."""
    values: dict[str, object] = {"x": "outer", "xs": [0, 1, 2], "ys": [10, 20]}
    node = parse_expression("[x + y for x in xs if x for y in ys]")
    assert await evaluate(node, values) == [11, 21, 12, 22]
    assert values["x"] == "outer"


@pytest.mark.asyncio
async def test_multilayer_comprehension_filters_nested_comprehension() -> None:
    """Nested heads inherit outer targets after every clause filter passes."""
    values = {
        "xs": [1, 2, 3],
        "ys": [2, 4],
        "zs": [2, 3, 4, 6],
    }
    node = parse_expression(
        "[[x * y + z for z in zs if z % y == 0] " "for x in xs if x % 2 == 1 for y in ys if y > x]"
    )

    assert await evaluate(node, values) == [[4, 6, 8], [8], [16]]


@pytest.mark.asyncio
async def test_multilayer_clauses_filter_nested_data_structures() -> None:
    """Each clause applies all filters while traversing nested mappings."""
    values = {
        "x": [
            [
                {"kind": "keep", "value": 1},
                {"kind": "drop", "value": 2},
                {"kind": "keep", "value": 4},
            ],
            [
                {"kind": "skip", "value": 6},
                {"kind": "keep", "value": 8},
            ],
            [
                {"kind": "keep", "value": 3},
                {"kind": "keep", "value": 10},
            ],
        ]
    }
    node = parse_expression(
        '[z["value"] for y in x '
        'if y[0]["kind"] != "skip" if y[0]["value"] < 5 '
        'for z in y if z["kind"] == "keep" if z["value"] % 2 == 0]'
    )

    assert await evaluate(node, values) == [4, 10]


@pytest.mark.asyncio
async def test_nested_starred_comprehensions_flatten_multiple_layers() -> None:
    """Nested starred heads flatten inner groups into one ordered list."""
    values = {
        "a": [
            [[1, 2], [3]],
            [[], [4, 5]],
            [[6], [7, 8]],
        ]
    }
    node = parse_expression("[*[*c for c in b] for b in a]")

    assert await evaluate(node, values) == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.asyncio
async def test_set_and_dict_comprehensions_materialize() -> None:
    """Set and dictionary heads retain their collection semantics."""
    values = {"xs": [1, 2, 2]}
    assert await evaluate(parse_expression("{x * 2 for x in xs}"), values) == {2, 4}
    assert await evaluate(parse_expression("{x: x * 2 for x in xs}"), values) == {
        1: 2,
        2: 4,
    }


@pytest.mark.asyncio
async def test_comprehension_accepts_async_iterable() -> None:
    """Async-only sources are consumed without a blocking adapter."""
    values = {"xs": AsyncValues([1, 2, 3])}
    assert await evaluate(parse_expression("[x * 2 for x in xs]"), values) == [2, 4, 6]


@pytest.mark.asyncio
async def test_pep798_heads_expand_values() -> None:
    """Starred sequence and double-star mapping heads flatten each iteration."""
    values = {"groups": [[1, 2], [3]], "mappings": [{"a": 1}, {"b": 2}]}
    listed = await evaluate(parse_expression("[*group for group in groups]"), values)
    mapping = await evaluate(
        parse_expression("{**mapping for mapping in mappings}"),
        values,
    )
    assert listed == [1, 2, 3]
    assert mapping == {"a": 1, "b": 2}


@pytest.mark.asyncio
async def test_dictionary_comprehension_rejects_non_mapping_unpack() -> None:
    """Every accepted binding must still produce a mapping for double-star expansion."""
    with pytest.raises(LclEvaluationError, match="requires a mapping") as caught:
        await evaluate(
            parse_expression("{**value for value in values}"),
            {"values": [{"ok": 1}, ["not", "mapping"]]},
        )
    assert isinstance(caught.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_dictionary_comprehension_rejects_invalid_ast_entry() -> None:
    """A manually malformed dictionary head is rejected instead of silently skipped."""
    valid = parse_expression("{**value for value in values}")
    assert isinstance(valid, LclDictComprehension)
    malformed = LclDictComprehension(
        LclConstant(value="invalid"),  # type: ignore[arg-type]
        valid.clauses,
        span=valid.span,
    )
    with pytest.raises(LclEvaluationError, match="unsupported dictionary comprehension entry"):
        await evaluate(malformed, {"values": [1]})


@pytest.mark.asyncio
async def test_generator_is_lazy_and_returns_async_iterator() -> None:
    """Clause and head evaluation begins only when the generator is consumed."""
    events: list[str] = []

    class LazyValues:
        def __iter__(self) -> Iterator[int]:
            events.append("iterate")
            yield 1
            yield 2

    generator = await evaluate(
        parse_expression("(x * 2 for x in xs)"),
        {"xs": LazyValues()},
    )
    assert events == []
    stream = cast(AsyncIterable[object], generator)
    assert [value async for value in stream] == [2, 4]
    assert events == ["iterate"]


@pytest.mark.asyncio
async def test_starred_comprehension_awaits_mapped_lcl_results() -> None:
    """PEP 798 flattening resolves every async function result from Python map."""
    result = await evaluate(
        parse_expression("[*map((x) -> x.lower(), group) for group in groups]"),
        {"map": map, "groups": [["A"], ["B", "C"]]},
    )
    for value in cast(list[object], result):
        if isawaitable(value):
            await cast(Awaitable[object], value)
    assert result == ["a", "b", "c"]
