"""Unit tests mirroring :mod:`pylcl.stdlib.iterables`."""

from collections.abc import AsyncIterator

import pytest

from pylcl.stdlib import collect, first


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
