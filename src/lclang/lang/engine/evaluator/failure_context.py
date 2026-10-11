"""Capture evaluation diagnostics before their first verbose observation.

Defines ``capture_node_failure``.
"""

from lclang.error import LclError
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.evaluator.definition_scope import active_definition_stack
from lclang.lang.engine.evaluator.evaluation_journal import capture_evaluation_context
from lclang.lang.engine.evaluator.evaluation_tracing import describe_evaluation_phase


def capture_node_failure(error: LclError, node: LclAstNode, *, phase: str | None = None) -> None:
    """Retain the ordinary failure scene without repeating an observed summary.

    :param error: Original classified failure whose diagnostic fields are preserved.
    :param node: Node at the actual failing operation or awaiting boundary.
    :param phase: Explicit awaiting phase, or None for the node's operation phase.
    """
    if error.span is None:
        error.span = node.span
    error.attach_variable_stack(active_definition_stack())
    if not error.evaluation_context:
        error.attach_evaluation_context(capture_evaluation_context())
    if error.verbose_failure_id is None:
        stack = active_definition_stack()
        trace_verbose_failure(
            error,
            stack[-1] if stack else "<expr>",
            phase=describe_evaluation_phase(node) if phase is None else phase,
        )
