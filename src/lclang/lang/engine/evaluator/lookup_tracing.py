"""Readable mapping and lexical input observations.

Defines ``trace_resolver_value``.
"""

from inspect import isawaitable

from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT
from lclang.error.verbose_diagnostic import internal_render_value, internal_verbose_enabled
from lclang.error.verbose_records import emit_verbose_record


def trace_resolver_value(
    name: str, result: object, *, local: bool = False, masked: bool = False
) -> None:
    """Describe a resolver read without resolving an additional awaitable.

    :param name: Actual input name requested by the evaluator.
    :param result: Existing resolver result, possibly still deferred for lexical inputs.
    :param local: Whether the binding belongs to a lexical scope.
    :param masked: Whether value rendering must be suppressed.
    """
    if not internal_verbose_enabled():
        return
    source = "local input" if local else "external input"
    evaluation_id = ACTIVE_VERBOSE_CONTEXT.get().evaluation_id
    identity = "" if evaluation_id is None else f" (evaluation {evaluation_id})"
    if local and isawaitable(result):
        emit_verbose_record(
            "lookup",
            f"Selected {name} from {source}; awaiting remains with the evaluator{identity}",
        )
    else:
        emit_verbose_record(
            "lookup",
            f"Read {name} from {source}: {internal_render_value(result, masked=masked)}{identity}",
        )
