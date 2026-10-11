"""Classify awaited failures at an owning library operation.

Defines ``resolve_operation_value``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error.exception_base import LclError
from lclang.utils.awaitable_resolution import resolve_awaitable

if TYPE_CHECKING:
    from lclang.lang.common.source_location import SourceSpan


async def resolve_operation_value(
    value: object, error_type: type[LclError], code: str, *, span: SourceSpan | None = None
) -> object:
    """Resolve a value and classify native failures at the supplied operation boundary.

    :param value: Immediate value or nested awaitable owned by the caller.
    :param error_type: Error family selected by the owning operation.
    :param code: Concrete native failure code selected by that operation.
    :param span: Optional source span retained in a newly wrapped failure.
    :returns: Final immediate value.
    :raises LclError: If an ordinary awaited failure occurs; existing codes are retained.
    :raises BaseException: If cancellation, iteration or process control propagates.
    """
    from lclang.error.exception_base import LclError
    from lclang.error.native_wrap import wrap_failure

    try:
        return await resolve_awaitable(value)
    except LclError:
        raise
    except Exception as error:
        failure = wrap_failure(error, error_type, code, span=span)
        raise failure from error
