"""Reviewed async helpers for synchronous and asynchronous iterables."""

from __future__ import annotations

from lclang.error import LclStandardError
from lclang.error.boundary import guard_async_failure
from lclang.error.codes.standard import Code as standard_codes
from lclang.lang.evaluator.iteration import iterate_values


@guard_async_failure(LclStandardError, standard_codes.NATIVE_931)
async def collect(values: object) -> list[object]:
    """Collect a synchronous or asynchronous iterable into a new list.

    :param values: Object implementing sync or async iteration.
    :returns: Fresh list containing every item in iteration order.
    :raises LclValidationError: If *values* supports neither iteration protocol.

    .. note::
       Async iteration is preferred by the shared evaluator iteration boundary.
    """
    return [item async for item in iterate_values(values)]


@guard_async_failure(LclStandardError, standard_codes.NATIVE_931)
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
