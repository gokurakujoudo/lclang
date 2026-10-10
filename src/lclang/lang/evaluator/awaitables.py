"""Automatic awaitable resolution shared by evaluator handlers."""

from __future__ import annotations

from collections.abc import Awaitable
from inspect import isawaitable
from typing import cast

from lclang.error import LclEvaluationError
from lclang.error.boundary import guard_async_failure
from lclang.error.codes.language import Code as language_codes


@guard_async_failure(LclEvaluationError, language_codes.NATIVE_132)
async def resolve_awaitable(value: object) -> object:
    """Resolve nested awaitables to their final immediate value.

    :param value: Immediate value or awaitable produced by evaluation.
    :returns: First recursively non-awaitable result.
    :raises BaseException: If an awaited operation raises or is cancelled.

    .. note::
       Immediate values are returned without creating a task or future.
    """
    result = value
    while isawaitable(result):
        result = await cast(Awaitable[object], result)
    return result
