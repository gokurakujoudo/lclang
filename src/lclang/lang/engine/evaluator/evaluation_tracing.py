"""Readable expression results and detecting-boundary failure phases.

Defines ``describe_evaluation_phase``, ``trace_evaluation_result``.
"""

from lclang.error.source_excerpt import render_source_location
from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT
from lclang.error.verbose_diagnostic import internal_render_value, internal_verbose_enabled
from lclang.error.verbose_guard import guard_verbose_operation
from lclang.error.verbose_records import emit_verbose_record
from lclang.lang.ast import LclAstNode, LclBinary, LclCall, LclCompare, LclName
from lclang.lang.engine.evaluator.display_capture import render_display_value
from lclang.lang.engine.evaluator.evaluation_journal import ACTIVE_TARGET_EXPRESSION
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


@guard_verbose_operation
def trace_evaluation_result(node: LclAstNode, result: object) -> None:
    """Describe a completed expression without repeating its AST payload.

    :param node: Expression whose evaluation just completed.
    :param result: Already-resolved result to protect before logging.
    """
    if not internal_verbose_enabled():
        return
    if node is ACTIVE_TARGET_EXPRESSION.get():
        return
    context = ACTIVE_VERBOSE_CONTEXT.get()
    name = context.request_path[-1] if context.request_path else "<expr>"
    heading = f"Evaluated {name}: {render_display_value(result)}"
    if context.evaluation_id is not None:
        heading += f" (evaluation {context.evaluation_id})"
    emit_verbose_record(
        "evaluate",
        heading,
        context_details=(
            ("Expression", internal_render_value(node, lambda: to_source(node))),
            ("Source", render_source_location(node.span)),
        ),
    )
