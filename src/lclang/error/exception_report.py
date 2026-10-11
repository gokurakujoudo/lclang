"""One diagnostic report shared by logging and explicit unhandled hooks.

Defines ``render_exception_report``, ``contains_lcl_failure``.
"""

from types import TracebackType
from typing import Literal, cast

from lclang.error.diagnostic_rendering import render_failure
from lclang.error.exception_base import LclError
from lclang.error.failure_traceback import render_failure_traceback
from lclang.error.native_wrap import is_ordinary_failure


def contains_lcl_failure(error: BaseException) -> bool:
    """Select ordinary LCL chains and groups without swallowing control signals.

    :param error: Original candidate exception graph.
    :returns: Whether every observed node is ordinary and any node is an LCL error.
    """
    pending = [error]
    seen: set[int] = set()
    found = False
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if not is_ordinary_failure(current):
            return False
        found = found or isinstance(current, LclError)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(cast(BaseExceptionGroup[BaseException], current).exceptions)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        elif current.__context__ is not None and not current.__suppress_context__:
            pending.append(current.__context__)
    return found


def render_exception_report(
    error: BaseException,
    tb: TracebackType | None,
    *,
    traceback_style: Literal["compact", "full"] = "compact",
) -> str:
    """Render full language evidence once and retain the selected Python stack.

    :param error: Original failure, retaining its native propagation state.
    :param tb: Traceback supplied by the reporting boundary.
    :param traceback_style: Compact module filtering or all Python frames.
    :returns: Diagnostic tree followed by Python evidence when frames exist.
    """
    diagnostic = render_failure(
        error, action="" if isinstance(error, LclError) else "handling failure"
    )
    trace = render_failure_traceback(error, tb, style=traceback_style, require_frames=True)
    return diagnostic + ("\nPython traceback:\n" + trace if trace else "")
