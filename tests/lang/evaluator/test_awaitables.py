"""Unit tests mirroring :mod:`pylcl.lang.evaluator.awaitables`."""

import pytest

from pylcl.lang.evaluator.awaitables import resolve_awaitable


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
