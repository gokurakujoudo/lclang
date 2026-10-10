"""Unit tests mirroring :mod:`lclang.lang.evaluator.iteration`."""

from collections.abc import AsyncIterator, Awaitable
from inspect import isawaitable
from typing import cast

import pytest

from lclang.error import LclEvaluationError
from lclang.lang.evaluator.iteration import iterate_values


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
    """Non-iterable inputs receive a specific structured failure."""
    with pytest.raises(LclEvaluationError):
        _ = [value async for value in iterate_values(42)]


@pytest.mark.asyncio
async def test_iteration_retains_a_callback_lcl_failure_without_self_cause() -> None:
    """An iterator's existing code and original cause survive propagation unchanged."""
    error = LclEvaluationError("iterator failed", code="APP")

    async def values() -> AsyncIterator[int]:
        yield 1
        raise error

    with pytest.raises(LclEvaluationError) as caught:
        _ = [value async for value in iterate_values(values())]
    assert caught.value is error and error.__cause__ is None


@pytest.mark.asyncio
async def test_native_iterator_failure_has_its_own_boundary_code() -> None:
    """Failure in the iteration callback is distinct from resolving a yielded awaitable."""
    native = OSError("iterator unavailable")

    async def values() -> AsyncIterator[int]:
        yield 1
        raise native

    with pytest.raises(LclEvaluationError) as caught:
        _ = [value async for value in iterate_values(values())]
    assert caught.value.code == "LCL135811" and caught.value.__cause__ is native


@pytest.mark.asyncio
async def test_iterate_values_resolves_sync_and_async_awaitable_items() -> None:
    """Every yielded item reaches consumers as a recursively immediate value."""

    async def lowered(value: str) -> str:
        return value.lower()

    async def asynchronous() -> AsyncIterator[object]:
        yield lowered("C")
        yield lowered("D")

    sync_result = [value async for value in iterate_values(map(lowered, ["A", "B"]))]
    async_result = [value async for value in iterate_values(asynchronous())]
    for value in (*sync_result, *async_result):
        if isawaitable(value):
            await cast(Awaitable[object], value)
    assert sync_result == ["a", "b"]
    assert async_result == ["c", "d"]


@pytest.mark.asyncio
async def test_iterate_values_propagates_awaitable_item_failure() -> None:
    """An exception raised while resolving an iterable item is not deferred."""

    async def broken() -> object:
        raise RuntimeError("broken mapped item")

    deferred = broken()
    try:
        with pytest.raises(LclEvaluationError, match="broken mapped item"):
            _ = [value async for value in iterate_values([deferred])]
    finally:
        deferred.close()
