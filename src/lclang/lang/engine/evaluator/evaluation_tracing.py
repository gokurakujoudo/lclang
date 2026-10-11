"""Readable expression results and detecting-boundary failure phases.

Defines ``describe_evaluation_phase``, ``trace_evaluation_result``.
"""

from lclang.error.source_excerpt import render_source_location
from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT
from lclang.error.verbose_diagnostic import internal_render_value, internal_verbose_enabled
from lclang.error.verbose_records import emit_verbose_record
from lclang.lang.ast import LclAstNode, LclBinary, LclCall, LclCompare, LclName
from lclang.lang.engine.printer import to_source


def describe_evaluation_phase(node: LclAstNode) -> str:
    """Describe the node actually executing when an ordinary failure is detected.

    :param node: Failing semantic node, without inspecting exception wording.
    :returns: Short English execution phase.
    """
    if isinstance(node, LclBinary):
        return "arithmetic operation"
    if isinstance(node, LclCompare):
        return "comparison operation"
    if isinstance(node, LclCall):
        return "calling a function"
    if isinstance(node, LclName):
        return "resolving a named input"
    return "evaluating an expression"


def trace_evaluation_result(node: LclAstNode, result: object) -> None:
    """Describe a completed expression without repeating its AST payload.

    :param node: Expression whose evaluation just completed.
    :param result: Already-resolved result to protect before logging.
    """
    if not internal_verbose_enabled():
        return
    context = ACTIVE_VERBOSE_CONTEXT.get()
    name = context.request_path[-1] if context.request_path else "<expr>"
    details = [
        ("Expression", internal_render_value(node, lambda: to_source(node))),
        ("Result", internal_render_value(result)),
    ]
    if str(node.span.origin.name) != "<unknown>":
        details.insert(0, ("Source", render_source_location(node.span)))
    if context.request_path:
        details.append(("Request", " -> ".join(context.request_path)))
    if context.evaluation_id is not None:
        details.append(("Evaluation", context.evaluation_id))
    emit_verbose_record("evaluate", f"Evaluated {name}", details=tuple(details))
