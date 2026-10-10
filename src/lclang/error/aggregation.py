"""Combine ordinary failures without converting process-control exceptions."""

from lclang.error.base import LclError, LclValidationError
from lclang.error.codes.general import Code as general_codes
from lclang.error.groups import LclErrorGroup
from lclang.error.wrapping import is_ordinary_failure, wrap_failure


def combine_failures(
    pending: BaseException | None,
    cleanup: BaseException,
    *,
    code: str = general_codes.GROUP,
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
            "failure aggregation requires exceptions", code=general_codes.GROUP_CONTENT
        )
    if pending is cleanup:
        return (
            wrap_failure(cleanup, LclError, general_codes.GROUP_MEMBER)
            if is_ordinary_failure(cleanup)
            else cleanup
        )
    if is_ordinary_failure(cleanup):
        cleanup = wrap_failure(cleanup, LclError, general_codes.GROUP_MEMBER)
    if pending is None:
        return cleanup
    if is_ordinary_failure(pending) and is_ordinary_failure(cleanup):
        return LclErrorGroup("execution and cleanup failed", [pending, cleanup], code=code)
    if is_ordinary_failure(pending):
        pending, cleanup = cleanup, pending
    if is_ordinary_failure(cleanup):
        cleanup = wrap_failure(cleanup, LclError, general_codes.GROUP_MEMBER)
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
