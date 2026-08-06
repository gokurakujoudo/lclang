"""Unit tests mirroring :mod:`pylcl.lang.evaluator.comprehensions`."""

from collections.abc import AsyncIterable, AsyncIterator, Iterator
from typing import cast

import pytest

from pylcl import evaluate
from pylcl.lang.parser import parse_expression


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
