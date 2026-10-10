"""Wrap native operation failures without replacing existing LCL diagnostics.

Defines ``is_ordinary_failure``, ``wrap_failure``.
"""

from typing import TYPE_CHECKING, TypeIs, cast

from lclang.error.exception_base import LclError

if TYPE_CHECKING:
    from lclang.common.source_location import SourceSpan


def is_ordinary_failure(error: BaseException) -> TypeIs[Exception]:
    """Identify ordinary failures while retaining native control and iterator signals.

    :param error: Exception encountered at an operation or cleanup boundary.
    :returns: Whether the exception is eligible for ordinary LCL wrapping/grouping.
    """
    if not isinstance(error, Exception) or isinstance(error, (StopIteration, StopAsyncIteration)):
        return False
    if isinstance(error, ExceptionGroup):
        group = cast(ExceptionGroup[Exception], error)
        return all(is_ordinary_failure(member) for member in group.exceptions)
    return True


def wrap_failure(
    error: Exception,
    error_type: type[LclError],
    code: str,
    *,
    span: SourceSpan | None = None,
    message: str | None = None,
) -> LclError:
    """Retain an LCL failure or detach one native failure at its boundary.

    :param error: Failure produced by the operation.
    :param error_type: LCL family used for a new wrapper.
    :param code: Classified operation failure code.
    :param span: Optional source range for the failing operation.
    :param message: Optional fixed operation description for a newly wrapped failure.
    :returns: Existing LCL error or wrapper preserving the native cause and traceback.
    """
    if isinstance(error, LclError):
        return error
    if not is_ordinary_failure(error):
        raise error
    if isinstance(error, ExceptionGroup):
        from lclang.error.exception_group import LclErrorGroup

        group = cast(ExceptionGroup[Exception], error)
        grouped = LclErrorGroup(
            message or group.message or type(group).__name__,
            [wrap_failure(member, error_type, code, span=span) for member in group.exceptions],
            code=code,
        )
        grouped.span = span
        grouped.freeze_native_cause(error)
        grouped.__cause__ = error
        grouped.__traceback__ = error.__traceback__
        return grouped
    result = error_type(type(error).__name__ if message is None else message, span=span, code=code)
    result.freeze_native_cause(error)
    result.message = (result.native_cause or type(error).__name__) if message is None else message
    result.args = (result.message,)
    result.__cause__ = error
    result.__traceback__ = error.__traceback__
    return result
