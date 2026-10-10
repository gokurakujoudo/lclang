"""Caller-specific load contexts without changing exception classes or causes."""

from copy import copy
from typing import cast

from lclang.error_context import ConfigLoadFrame
from lclang.errors import LclError
from lclang.source import SourceSpan
from lclang.source_rendering import render_source_excerpt, render_source_location


def derive_loading_error(error: Exception, frame: ConfigLoadFrame) -> Exception:
    """Add one immutable loading placement to a detached failure copy.

    :param error: Structured language error or native configuration validation error.
    :param frame: Root or introduction placement for this caller only.
    :returns: Same exception class with original cause, traceback, and loading path.
    """
    if isinstance(error, LclError):
        return error.derive_config_context(frame)
    result = copy(error)
    previous = cast(tuple[ConfigLoadFrame, ...], getattr(error, "config_stack", ()))
    stack = (frame, *previous)
    reason = cast(str, getattr(error, "failure_reason", str(error)))
    lines = [f'Error in loading config file "{stack[0].origin.name}" [{type(error).__name__}]:']
    for item in stack:
        if item.declaration_span is not None:
            lines.append("  at " + render_source_location(item.declaration_span))
            lines.extend(
                "    " + line
                for line in render_source_excerpt(item.declaration_span, underline=False)
            )
    span = error.__dict__.get("source_span")
    if isinstance(span, SourceSpan):
        lines.append("  at " + render_source_location(span))
        lines.extend("    " + line for line in render_source_excerpt(span))
    lines.append("Cause: " + reason)
    result.args = ("\n".join(lines),)
    result.__cause__ = error.__cause__
    result.__context__ = error.__context__
    result.__suppress_context__ = error.__suppress_context__
    result.__traceback__ = error.__traceback__
    if hasattr(error, "__notes__"):
        result.__notes__ = list(error.__notes__)
    result.__dict__.update({"config_stack": stack, "failure_reason": reason})
    return result
