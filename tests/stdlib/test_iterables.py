"""Unit tests mirroring :mod:`lclang.stdlib.iterables`."""

from collections.abc import AsyncIterator, Awaitable
from inspect import isawaitable
from typing import cast

import pytest

from lclang.stdlib import collect, first


@pytest.mark.asyncio
async def test_collect_consumes_sync_and_async_iterables_in_order() -> None:
    """Collection always returns a fresh ordered list."""

    async def asynchronous() -> AsyncIterator[int]:
        yield 1
        yield 2

    source = [3, 4]
    assert await collect(asynchronous()) == [1, 2]
    result = await collect(source)
    assert result == source and result is not source


@pytest.mark.asyncio
async def test_first_stops_early_and_returns_default_for_empty_input() -> None:
    """Only the first async item is requested when one exists."""
    consumed: list[int] = []

    async def values() -> AsyncIterator[int]:
        for value in (1, 2):
            consumed.append(value)
            yield value

    assert await first(values()) == 1
    assert consumed == [1]
    marker = object()
    assert await first((), marker) is marker


@pytest.mark.asyncio
async def test_iterable_helpers_reject_non_iterable_values() -> None:
    """Iteration protocol errors propagate without silent coercion."""
    with pytest.raises(TypeError):
        await collect(1)
    with pytest.raises(TypeError):
        await first(1)


@pytest.mark.asyncio
async def test_iterable_helpers_await_python_map_items() -> None:
    """Collect and first resolve async values yielded by a lazy Python map."""

    async def lowered(value: str) -> str:
        return value.lower()

    collected = await collect(map(lowered, ["A", "B"]))
    selected = await first(map(lowered, ["C", "D"]))
    for value in (*collected, selected):
        if isawaitable(value):
            await cast(Awaitable[object], value)
    assert collected == ["a", "b"]
    assert selected == "c"
