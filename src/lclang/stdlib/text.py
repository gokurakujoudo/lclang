"""Reviewed deterministic text helpers for the standard preset."""

from __future__ import annotations

from lclang.error import LclStandardError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_failure
from lclang.error.codes.standard import Code as standard_codes
from lclang.lang.evaluator.iteration import iterate_values


@guard_async_failure(LclStandardError, standard_codes.NATIVE_961)
async def join(separator: str, values: object) -> str:
    """Join synchronous or asynchronous string values in order.

    :param separator: String placed between adjacent items.
    :param values: Sync or async iterable containing only strings.
    :returns: Joined text.
    :raises LclValidationError: If the separator or an item is not a string.

    .. note::
       Values are never stringified implicitly.
    """
    if not isinstance(separator, str):
        raise LclValidationError(
            "text separator must be a string",
            code=standard_codes.E61_TEXT_SEPARATOR_MUST_BE_A_STRING,
        )
    items: list[str] = []
    async for item in iterate_values(values):
        if not isinstance(item, str):
            raise LclValidationError(
                "text join items must be strings",
                code=standard_codes.E61_TEXT_SEPARATOR_MUST_BE_A_STRING,
            )
        items.append(item)
    return separator.join(items)


@guard_failure(LclStandardError, standard_codes.NATIVE_961)
def lines(value: str, *, keep_ends: bool = False) -> list[str]:
    """Split text at Unicode line boundaries.

    :param value: Text to split.
    :param keep_ends: Whether each result retains its line boundary.
    :returns: Fresh line list using :meth:`str.splitlines` semantics.
    :raises LclValidationError: If *value* is not text or *keep_ends* is not boolean.

    .. note::
       Empty terminal lines follow Python's deterministic splitlines contract.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "lines value must be a string", code=standard_codes.E61_TEXT_SEPARATOR_MUST_BE_A_STRING
        )
    if type(keep_ends) is not bool:
        raise LclValidationError(
            "keep_ends must be a boolean", code=standard_codes.E61_KEEP_ENDS_MUST_BE_A_BOOLEAN
        )
    return value.splitlines(keepends=keep_ends)
