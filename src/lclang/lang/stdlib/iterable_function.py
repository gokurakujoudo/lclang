"""Reviewed async helpers for synchronous and asynchronous iterables.

Defines ``collect``, ``first``.
"""

from __future__ import annotations

from lclang.error import LclStandardError, StandardLibraryErrorCode
from lclang.error.operation_guard import guard_async_failure
from lclang.lang.engine.evaluator.value_iteration import iterate_values


@guard_async_failure(
    LclStandardError, StandardLibraryErrorCode.E31_ITERABLE_FUNCTION_NATIVE_FAILURE
)
async def collect(values: object) -> list[object]:
    """Collect a synchronous or asynchronous iterable into a new list.

    :param values: Object implementing sync or async iteration.
    :returns: Fresh list containing every item in iteration order.
    :raises LclValidationError: If *values* supports neither iteration protocol.

    .. note::
       Async iteration is preferred by the shared evaluator iteration boundary.
    """
    return [item async for item in iterate_values(values)]


@guard_async_failure(
    LclStandardError, StandardLibraryErrorCode.E31_ITERABLE_FUNCTION_NATIVE_FAILURE
)
async def first(values: object, default: object = None) -> object:
    """Return the first iterable item without consuming later items.

    :param values: Object implementing sync or async iteration.
    :param default: Value returned when iteration is empty.
    :returns: First item or *default* when no item exists.
    :raises LclValidationError: If *values* supports neither iteration protocol.

    .. note::
       Iteration stops immediately after the first yielded item.
    """
    async for item in iterate_values(values):
        return item
    return default
