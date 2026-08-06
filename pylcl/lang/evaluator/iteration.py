"""Uniform asynchronous iteration over sync and async application values."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import cast


async def iterate_values(value: object) -> AsyncIterator[object]:
    """Yield values from an asynchronous or synchronous iterable.

    :param value: Object providing ``__aiter__`` or ``__iter__``.
    :returns: Async iterator preserving the input's iteration order.
    :raises TypeError: If *value* supports neither iteration protocol.

    .. note::
       Async iteration is preferred when an object implements both protocols.
    """
    if isinstance(value, AsyncIterable):
        async for item in value:
            yield item
        return
    for item in cast(Iterable[object], value):
        yield item
