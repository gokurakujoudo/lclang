"""Unit tests mirroring :mod:`pylcl.lang.evaluator.iteration`."""

from collections.abc import AsyncIterator

import pytest

from pylcl.lang.evaluator.iteration import iterate_values


class AsyncValues:
    """Yield stored values through the asynchronous iteration protocol."""

    def __init__(self, values: list[int]) -> None:
        """Store values for later asynchronous iteration."""
        self.values = values

    async def __aiter__(self) -> AsyncIterator[int]:
        """Yield values without a synchronous iterator."""
        for value in self.values:
            yield value


@pytest.mark.asyncio
async def test_iterate_values_adapts_sync_and_async_protocols() -> None:
    """One async stream boundary preserves both supported input orders."""
    sync_result = [value async for value in iterate_values([1, 2])]
    async_result = [value async for value in iterate_values(AsyncValues([3, 4]))]
    assert sync_result == [1, 2]
    assert async_result == [3, 4]


@pytest.mark.asyncio
async def test_iterate_values_rejects_non_iterable() -> None:
    """Invalid values retain the ordinary iteration TypeError."""
    with pytest.raises(TypeError):
        _ = [value async for value in iterate_values(42)]
