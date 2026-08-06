"""Reviewed deterministic text helpers for the standard preset."""

from __future__ import annotations

from pylcl.lang.evaluator.iteration import iterate_values


async def join(separator: str, values: object) -> str:
    """Join synchronous or asynchronous string values in order.

    :param separator: String placed between adjacent items.
    :param values: Sync or async iterable containing only strings.
    :returns: Joined text.
    :raises TypeError: If the separator or an item is not a string.

    .. note::
       Values are never stringified implicitly.
    """
    if not isinstance(separator, str):
        raise TypeError("text separator must be a string")
    items: list[str] = []
    async for item in iterate_values(values):
        if not isinstance(item, str):
            raise TypeError("text join items must be strings")
        items.append(item)
    return separator.join(items)


def lines(value: str, *, keep_ends: bool = False) -> list[str]:
    """Split text at Unicode line boundaries.

    :param value: Text to split.
    :param keep_ends: Whether each result retains its line boundary.
    :returns: Fresh line list using :meth:`str.splitlines` semantics.
    :raises TypeError: If *value* is not text or *keep_ends* is not boolean.

    .. note::
       Empty terminal lines follow Python's deterministic splitlines contract.
    """
    if not isinstance(value, str):
        raise TypeError("lines value must be a string")
    if type(keep_ends) is not bool:
        raise TypeError("keep_ends must be a boolean")
    return value.splitlines(keepends=keep_ends)
