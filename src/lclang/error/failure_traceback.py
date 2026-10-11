"""Python stacks with concise LCL references beside a complete diagnostic.

Defines ``render_failure_traceback``, ``render_traceback_branch``.
"""

import traceback
from types import TracebackType
from typing import cast

from lclang.error.exception_base import LclError


def render_failure_traceback(error: BaseException, tb: TracebackType | None) -> str:
    """Render Python execution evidence without repeating LCL diagnostic paragraphs.

    :param error: Original exception with its causes, contexts and group members.
    :param tb: Original traceback selected by the logging record.
    :returns: Python stack and exception-chain text with concise LCL leaves.
    """
    return "\n".join(render_traceback_branch(error, tb, frozenset()))


def render_traceback_branch(
    error: BaseException, tb: TracebackType | None, ancestors: frozenset[int]
) -> list[str]:
    """Render one exception branch while retaining native chain and group structure.

    :param error: Original exception at this branch.
    :param tb: Original branch traceback.
    :param ancestors: Already-rendering ancestor identities, used only to stop native cycles.
    :returns: Stack, concise exception label and recursively retained member lines.
    """
    if id(error) in ancestors:
        return [f"{type(error).__name__}: exception-chain cycle"]
    selected = ancestors | {id(error)}
    lines: list[str] = []
    cause = error.__cause__
    context = error.__context__
    if cause is not None:
        lines.extend(render_traceback_branch(cause, cause.__traceback__, selected))
        lines.append("\nThe above exception was the direct cause of the following exception:\n")
    elif context is not None and not error.__suppress_context__:
        lines.extend(render_traceback_branch(context, context.__traceback__, selected))
        lines.append("\nDuring handling of the above exception, another exception occurred:\n")
    if tb is not None:
        lines.append("Traceback (most recent call last):")
        lines.extend("".join(traceback.format_tb(tb)).rstrip().splitlines())
    if isinstance(error, LclError):
        identity = (
            "" if error.verbose_failure_id is None else f" (failure {error.verbose_failure_id})"
        )
        lines.append(f"{type(error).__name__}: [{error.code}]{identity}")
    else:
        lines.extend("".join(traceback.format_exception_only(error)).rstrip().splitlines())
    if isinstance(error, BaseExceptionGroup):
        group = cast(BaseExceptionGroup[BaseException], error)
        for index, member in enumerate(group.exceptions, 1):
            lines.append(f"  Failure {index}:")
            lines.extend(
                "    " + line
                for line in render_traceback_branch(member, member.__traceback__, selected)
            )
    return lines
