"""Central precedence dispatch for canonical LCL source rendering."""

from __future__ import annotations

from collections.abc import Callable

from lclang.ast import LclAstNode
from lclang.error import LclEvaluationError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.language import Code as language_codes
from lclang.lang.printer._types import RenderResult
from lclang.lang.printer.atoms import render_atom
from lclang.lang.printer.collections import render_collection
from lclang.lang.printer.expressions import render_expression
from lclang.lang.printer.forms import render_form
from lclang.lang.printer.primaries import render_primary

type FamilyRenderer = Callable[[LclAstNode, Callable[[LclAstNode, int], str]], RenderResult | None]

# Unitless renderer order follows disjoint AST families; the tuple selects the first renderer
# accepting the expression.
_RENDERERS: tuple[FamilyRenderer, ...] = (
    render_atom,
    render_expression,
    render_primary,
    render_collection,
    render_form,
)


@guard_failure(LclEvaluationError, language_codes.NATIVE_141)
def to_source(node: LclAstNode) -> str:
    """Return deterministic canonical source for one semantic AST node.

    :param node: Root node to render.
    :returns: Canonical LCL V1 expression source.
    :raises LclValidationError: If the tree contains an unsupported node or value.

    .. note::
       Source spans are intentionally omitted because canonicalization may alter them.
    """
    return internal_render(node, 0)


def internal_render(node: LclAstNode, parent_precedence: int) -> str:
    """Dispatch one node and add parentheses required by its context.

    :param node: AST node to render.
    :param parent_precedence: Minimum precedence accepted without grouping.
    :returns: Canonical source text for the node.
    :raises LclValidationError: If no registered renderer supports the node.

    .. note::
       Renderer order resolves node families, while the returned precedence
       determines whether the rendered text needs enclosing parentheses.
    """
    for renderer in _RENDERERS:
        result = renderer(node, internal_render)
        if result is not None:
            text, precedence = result
            return f"({text})" if precedence < parent_precedence else text
    raise LclValidationError(
        f"unsupported AST node: {type(node).__name__}",
        code=language_codes.E41_UNSUPPORTED_AST_NODE_VALUE,
    )
