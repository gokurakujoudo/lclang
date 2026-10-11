"""Unit tests mirroring :mod:`lclang.utils.awaitable_resolution`."""

import asyncio

import pytest

from lclang.utils.awaitable_resolution import resolve_awaitable


@pytest.mark.asyncio
async def test_immediate_value_is_returned_unchanged() -> None:
    """Ordinary values do not require task scheduling or copying."""
    value = object()
    assert await resolve_awaitable(value) is value


@pytest.mark.asyncio
async def test_nested_awaitables_resolve_to_final_value() -> None:
    """Handlers may return awaitables that themselves produce awaitables."""

    async def inner() -> int:
        return 42

    async def outer() -> object:
        return inner()

    assert await resolve_awaitable(outer()) == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "signal",
    [OSError("native"), asyncio.CancelledError("cancel"), StopAsyncIteration("end")],
)
async def test_nested_awaitables_preserve_failure_identity(signal: BaseException) -> None:
    """The public resolver does not classify native failures or control signals."""

    async def inner() -> object:
        raise signal

    async def outer() -> object:
        return inner()

    with pytest.raises(type(signal)) as caught:
        await resolve_awaitable(outer())
    assert caught.value is signal
