"""Uniform asynchronous iteration over sync and async application values.

Defines ``iterate_values``.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import cast

from lclang.common.awaitable_resolution import resolve_awaitable
from lclang.error import LanguageErrorCode, LclError, LclEvaluationError
from lclang.error.native_wrap import wrap_failure


async def iterate_values(value: object) -> AsyncIterator[object]:
    """Yield values from an asynchronous or synchronous iterable.

    :param value: Object providing ``__aiter__`` or ``__iter__``.
    :returns: Async iterator preserving the input's iteration order.
    :raises LclEvaluationError: If iteration is unavailable or fails.

    .. note::
       Async iteration is preferred when an object implements both protocols.
       Every yielded item is recursively resolved before reaching its consumer.
    """
    if not isinstance(value, (AsyncIterable, Iterable)):
        raise LclEvaluationError("value is not iterable", code=LanguageErrorCode.E35_NOT_ITERABLE)
    try:
        if isinstance(value, AsyncIterable):
            async for item in cast(AsyncIterable[object], value):
                yield await resolve_awaitable(item)
            return
        for item in cast(Iterable[object], value):
            yield await resolve_awaitable(item)
    except LclError:
        raise
    except Exception as error:
        raise wrap_failure(
            error, LclEvaluationError, LanguageErrorCode.E35_ITERATION_FAILURE
        ) from error
