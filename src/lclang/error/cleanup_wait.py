"""Settle owned asynchronous cleanup before returning any pending control signal.

Defines ``settle_cleanup``.
"""

import asyncio
from collections.abc import Awaitable

from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.exception_base import LclError
from lclang.error.failure_aggregation import combine_failures
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure


async def settle_cleanup(
    operation: Awaitable[None],
    *,
    error_type: type[LclError] = LclError,
    code: str = GeneralErrorCode.E21_GROUP_MEMBER,
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
