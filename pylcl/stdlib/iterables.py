"""Reviewed async helpers for synchronous and asynchronous iterables."""

from __future__ import annotations

from pylcl.lang.evaluator.iteration import iterate_values


async def collect(values: object) -> list[object]:
    """Collect a synchronous or asynchronous iterable into a new list.

    :param values: Object implementing sync or async iteration.
    :returns: Fresh list containing every item in iteration order.
    :raises TypeError: If *values* supports neither iteration protocol.

    .. note::
       Async iteration is preferred by the shared evaluator iteration boundary.
    """
    return [item async for item in iterate_values(values)]


async def first(values: object, default: object = None) -> object:
    """Return the first iterable item without consuming later items.

    :param values: Object implementing sync or async iteration.
    :param default: Value returned when iteration is empty.
    :returns: First item or *default* when no item exists.
    :raises TypeError: If *values* supports neither iteration protocol.

    .. note::
       Iteration stops immediately after the first yielded item.
    """
    async for item in iterate_values(values):
        return item
    return default
