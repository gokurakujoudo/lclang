"""Combine ordinary failures without converting process-control exceptions.

Defines ``contains_failure``, ``combine_failures``.
"""

from typing import cast

from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.exception_base import LclError, LclValidationError
from lclang.error.exception_group import LclErrorGroup
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure


def contains_failure(error: BaseException, failure: BaseException) -> bool:
    """Check whether an existing group already retains a failure by identity.

    :param error: Existing failure or nested group.
    :param failure: Candidate exception or its native-member wrapper.
    :returns: Whether the same failure is already present, without comparing messages.
    """
    if isinstance(failure, LclError) and not isinstance(failure, LclErrorGroup):
        failure = failure.__cause__ or failure
    if error is failure or (isinstance(error, LclError) and error.__cause__ is failure):
        return True
    return isinstance(error, BaseExceptionGroup) and any(
        contains_failure(member, failure)
        for member in cast(BaseExceptionGroup[BaseException], error).exceptions
    )


def combine_failures(
    pending: BaseException | None,
    cleanup: BaseException,
    *,
    code: str = GeneralErrorCode.E21_GROUP,
) -> BaseException:
    """Retain execution and cleanup failures, keeping control-signal identity.

    :param pending: Failure already propagating, or None after successful execution.
    :param cleanup: Failure raised while closing an owned resource.
    :param code: Registered or application-defined code for an ordinary combined group.
    :returns: Original control exception or structured ordinary failure/group.
    :raises LclValidationError: If either argument is not an exception or None as allowed.
    """
    if (pending is not None and not isinstance(pending, BaseException)) or not isinstance(
        cleanup, BaseException
    ):
        raise LclValidationError(
            "failure aggregation requires exceptions", code=GeneralErrorCode.E21_GROUP_CONTENT
        )
    if pending is cleanup:
        return (
            wrap_failure(cleanup, LclError, GeneralErrorCode.E21_GROUP_MEMBER)
            if is_ordinary_failure(cleanup)
            else cleanup
        )
    if is_ordinary_failure(cleanup):
        cleanup = wrap_failure(cleanup, LclError, GeneralErrorCode.E21_GROUP_MEMBER)
    if pending is None:
        return cleanup
    if contains_failure(cleanup, pending):
        return cleanup
    if contains_failure(pending, cleanup):
        return pending
    if is_ordinary_failure(pending) and is_ordinary_failure(cleanup):
        return LclErrorGroup("execution and cleanup failed", [pending, cleanup], code=code)
    if is_ordinary_failure(pending):
        pending, cleanup = cleanup, pending
    if is_ordinary_failure(cleanup):
        cleanup = wrap_failure(cleanup, LclError, GeneralErrorCode.E21_GROUP_MEMBER)
    previous = pending.__cause__
    if cleanup.__context__ is pending:
        cleanup.__context__ = None
    if previous is None:
        pending.__cause__ = cleanup
    elif is_ordinary_failure(previous) and is_ordinary_failure(cleanup):
        pending.__cause__ = LclErrorGroup("cleanup failures", [previous, cleanup], code=code)
    else:
        pending.__cause__ = BaseExceptionGroup("cleanup failures", [previous, cleanup])
    return pending
