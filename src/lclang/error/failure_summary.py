"""Protected inline reasons and identities for human exception displays.

Defines ``describe_failure_reason``, ``render_failure_summary``.
"""

from lclang.error.exception_base import LclError


def describe_failure_reason(
    error: BaseException, *, masked: bool = False, max_length: int | None = 200
) -> str:
    """Render the original frozen cause or message as a bounded single line.

    :param error: Failure with optional detached LCL cause evidence.
    :param masked: Additional redaction inherited from the containing diagnostic.
    :param max_length: Existing summary budget, or None for complete exception details.
    :returns: Protected short reason without changing the exception or its traceback.
    """
    from lclang.utils.value_representation import safe_repr

    if isinstance(error, LclError):
        masked = masked or error.masked or any(frame.masked for frame in error.evaluation_context)
        reason = error.native_cause or error.message
        if error.native_cause is not None and error.__cause__ is not None:
            cause = error.__cause__
            seen: set[int] = set()
            while (
                isinstance(cause, LclError)
                and cause.__cause__ is not None
                and id(cause) not in seen
            ):
                seen.add(id(cause))
                cause = cause.__cause__
            reason = reason.removeprefix(type(cause).__name__ + ": ")
        return safe_repr(reason, renderer=str, masked=masked, max_length=max_length)
    return safe_repr(error, renderer=str, masked=masked, max_length=max_length)


def render_failure_summary(error: BaseException, *, masked: bool = False) -> str:
    """Render a concise exception reference with its reason alongside its code.

    :param error: Original native or LCL failure.
    :param masked: Additional inherited reason redaction.
    :returns: Single-line type, code, protected reason and optional failure identifier.
    """
    reason = describe_failure_reason(error, masked=masked)
    if not isinstance(error, LclError):
        return f"{type(error).__name__}: {reason}"
    identity = "" if error.verbose_failure_id is None else f" (failure {error.verbose_failure_id})"
    return f"{type(error).__name__} [{error.code}: {reason}]{identity}"
