"""Unit tests mirroring :mod:`lclang.stdlib.text`."""

from collections.abc import AsyncIterator

import pytest

from lclang.stdlib import join, lines


@pytest.mark.asyncio
async def test_join_consumes_sync_and_async_string_values() -> None:
    """Joining preserves source iteration order for both protocols."""

    async def words() -> AsyncIterator[str]:
        yield "alpha"
        yield "beta"

    assert await join("-", words()) == "alpha-beta"
    assert await join("/", ["a", "b"]) == "a/b"


@pytest.mark.asyncio
async def test_join_rejects_non_string_separator_or_items() -> None:
    """Text helpers do not stringify application values implicitly."""
    with pytest.raises(TypeError):
        await join(1, ["value"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        await join(",", ["value", 2])


def test_lines_uses_deterministic_splitlines_and_strict_types() -> None:
    """Line boundary retention follows the explicit boolean flag."""
    assert lines("a\r\nb\n") == ["a", "b"]
    assert lines("a\r\nb\n", keep_ends=True) == ["a\r\n", "b\n"]
    with pytest.raises(TypeError):
        lines(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        lines("value", keep_ends=1)  # type: ignore[arg-type]
