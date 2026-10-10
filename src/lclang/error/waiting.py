"""Settle owned asynchronous cleanup before returning any pending control signal."""

import asyncio
from collections.abc import Awaitable

from lclang.error.aggregation import combine_failures
from lclang.error.base import LclError
from lclang.error.codes.general import Code as general_codes
from lclang.error.wrapping import is_ordinary_failure, wrap_failure


async def settle_cleanup(
    operation: Awaitable[None],
    *,
    error_type: type[LclError] = LclError,
    code: str = general_codes.GROUP_MEMBER,
) -> BaseException | None:
    """Shield owned cleanup through repeated waiter cancellation.

    :param operation: Cleanup work whose completion the caller owns.
    :param error_type: Owner-selected family for native cleanup failures.
    :param code: Owner-selected code for native cleanup failures.
    :returns: Retained cancellation/cleanup failure, or None after success.
    """
    try:
        task = asyncio.ensure_future(operation)
    except Exception as error:
        return wrap_failure(error, error_type, code)
    failure: BaseException | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            failure = combine_failures(failure, error)
        except BaseException:
            break
    try:
        task.result()
    except BaseException as error:
        cleanup = wrap_failure(error, error_type, code) if is_ordinary_failure(error) else error
        failure = combine_failures(failure, cleanup)
    return failure
