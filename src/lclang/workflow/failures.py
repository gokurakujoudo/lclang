"""Preserve workflow failures while resource scopes unwind."""


def combine_failures(pending: BaseException | None, cleanup: BaseException) -> BaseException:
    """Retain both failures without converting process control to an ordinary error.

    :param pending: Failure already propagating through the resource scope.
    :param cleanup: Failure raised while exiting that scope.
    :returns: Ordinary exception group or original process-control exception with causes.
    """
    if pending is None or pending is cleanup:
        return cleanup
    if isinstance(pending, Exception) and isinstance(cleanup, Exception):
        return ExceptionGroup("workflow execution and cleanup failed", [pending, cleanup])
    if isinstance(pending, Exception):
        pending, cleanup = cleanup, pending
    previous = pending.__cause__
    if cleanup.__context__ is pending:
        cleanup.__context__ = None
    pending.__cause__ = (
        cleanup
        if previous is None
        else BaseExceptionGroup(
            "workflow cleanup failures",
            [previous, cleanup],
        )
    )
    return pending
