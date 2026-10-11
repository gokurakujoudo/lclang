"""Actual host invocation scopes spanning calls and recursive auto-awaiting.

Defines ``invoke_python_call``, ``is_read_value_masked``.
"""

from collections.abc import Callable
from typing import cast

from lclang.error import LclError
from lclang.error.mask_scope import ACTIVE_MASKED_VALUE
from lclang.error.native_wrap import is_ordinary_failure
from lclang.lang.ast import LclCall
from lclang.lang.engine.evaluator.display_requests import scope_display_expression
from lclang.lang.engine.evaluator.error_form_evaluation import internal_wrap_failure
from lclang.lang.engine.evaluator.evaluation_journal import (
    ACTIVE_EVALUATION_CONTEXT,
    collect_evaluation_context,
    record_value_read,
)
from lclang.lang.engine.evaluator.failure_context import capture_node_failure
from lclang.utils.awaitable_resolution import resolve_awaitable
from lclang.utils.python_callable_definition import describe_python_callable, render_python_callable


async def invoke_python_call(
    node: LclCall, target: object, positional: list[object], keywords: dict[str, object]
) -> object:
    """Capture an executed host call without adding resolution or argument binding.

    :param node: Actual LCL call site, whose arguments have already run.
    :param target: Resolved host callable.
    :param positional: Actual expanded positional arguments.
    :param keywords: Actual expanded keyword arguments.
    :returns: Recursively awaited result of the single invocation.
    :raises LclError: If the existing invocation or awaiting boundary fails.
    """
    span = node.function.span
    name = "<Python call>"
    if span.snapshot is not None:
        start = span.start.offset - span.snapshot.start.offset
        end = span.end.offset - span.snapshot.start.offset
        name = span.snapshot.text[start:end] or name
    target_hidden = is_read_value_masked(target)
    definition = None if target_hidden else describe_python_callable(target)
    summary = "*masked*" if target_hidden else render_python_callable(target)
    with (
        scope_display_expression(name, node, call=True) as display,
        collect_evaluation_context(
            name, node, kind="python-call", callable_definition=definition, callable_summary=summary
        ),
    ):
        if display is not None:
            display.label = f"{name}: {summary or 'Python callable'}"
        for index, value in enumerate(positional):
            record_value_read(
                f"arg[{index}]",
                value,
                node.span,
                masked=is_read_value_masked(value),
                source="argument",
            )
        for key, value in keywords.items():
            record_value_read(
                key, value, node.span, masked=is_read_value_masked(value), source="argument"
            )
        phase = "calling a function"
        try:
            result = cast(Callable[..., object], target)(*positional, **keywords)
            phase = "awaiting function result"
            return await resolve_awaitable(result)
        except Exception as error:
            if not is_ordinary_failure(error):
                raise
            failure = (
                error
                if isinstance(error, LclError)
                else internal_wrap_failure(error, node.span, node=node)
            )
            capture_node_failure(failure, node, phase=phase)
            if failure is error:
                raise
            raise failure from error


def is_read_value_masked(value: object) -> bool:
    """Protect aliases of values already read under masking.

    :param value: Actual argument or callable, without another lookup.
    :returns: Whether inherited scope or recorded input protection covers the value.
    """
    return ACTIVE_MASKED_VALUE.get() or any(
        read is value and protected
        for journal in ACTIVE_EVALUATION_CONTEXT.get()
        for read, protected, _ in journal.reads.values()
    )
