"""Typed synchronous and asynchronous callback invocation."""

from collections.abc import Awaitable, Callable
from typing import overload


@overload
async def invoke[**Params, Result](  # noqa: D418
    callback: Callable[Params, Awaitable[Result]], *args: Params.args, **kwargs: Params.kwargs,
) -> Result:
    """Retain parameters and the awaited result of an asynchronous callback.

    :param callback: Callback producing an awaitable.
    :param args: Positional callback arguments.
    :param kwargs: Keyword callback arguments.
    :returns: Resolved callback result.
    """
    ...


@overload
async def invoke[**Params, Result](  # noqa: D418
    callback: Callable[Params, Result], *args: Params.args, **kwargs: Params.kwargs,
) -> Result:
    """Retain parameters and the return type of a synchronous callback.

    :param callback: Callback producing an immediate value.
    :param args: Positional callback arguments.
    :param kwargs: Keyword callback arguments.
    :returns: Callback result.
    """
    ...


async def invoke[**Params](
    callback: Callable[Params, object], *args: Params.args, **kwargs: Params.kwargs,
) -> object:
    """Call once and recursively resolve awaitables in the current task.

    :param callback: Synchronous or asynchronous callable.
    :param args: Positional callback arguments, forwarded unchanged.
    :param kwargs: Keyword callback arguments, forwarded unchanged.
    :returns: Final non-awaitable value without copying or background work.
    :raises BaseException: If invocation or awaiting fails, including cancellation.
    """
    from lclang.lang.evaluator.awaitables import resolve_awaitable

    return await resolve_awaitable(callback(*args, **kwargs))
