"""Canonical rendering for chained primaries and call arguments."""

from __future__ import annotations

from lclang.ast import (
    LclAstNode,
    LclAttribute,
    LclCall,
    LclKeywordArgument,
    LclKeywordUnpackArgument,
    LclPositionalArgument,
    LclSafeAttribute,
    LclSlice,
    LclStarArgument,
    LclSubscript,
    LclTuple,
)
from lclang.lang.printer._types import Render, RenderResult

# Unitless precedence 90 matches primary expressions in the parser; the rank keeps calls,
# attributes and subscripts bound together.
PRIMARY_PRECEDENCE = 90


def render_primary(node: LclAstNode, render: Render) -> RenderResult | None:
    """Render an attribute, subscription, slice, or call.

    :param node: Candidate AST node.
    :param render: Recursive dispatcher applying parent precedence.
    :returns: Canonical source and precedence, or ``None`` for another family.

    .. note::
       Argument wrappers and slice omissions are rendered explicitly.
    """
    if isinstance(node, (LclAttribute, LclSafeAttribute)):
        operator = "?." if isinstance(node, LclSafeAttribute) else "."
        return f"{render(node.value, PRIMARY_PRECEDENCE)}{operator}{node.name}", PRIMARY_PRECEDENCE
    if isinstance(node, LclSubscript):
        index = internal_index(node.index, render)
        return f"{render(node.value, PRIMARY_PRECEDENCE)}[{index}]", PRIMARY_PRECEDENCE
    if isinstance(node, LclCall):
        arguments = ", ".join(internal_argument(argument, render) for argument in node.arguments)
        return f"{render(node.function, PRIMARY_PRECEDENCE)}({arguments})", PRIMARY_PRECEDENCE
    if isinstance(node, LclSlice):
        return internal_slice(node, render), PRIMARY_PRECEDENCE
    return None


def internal_argument(node: LclAstNode, render: Render) -> str:
    """Render one positional, starred, keyword, or unpacked argument.

    :param node: Call-argument wrapper to render.
    :param render: Recursive dispatcher for the argument value.
    :returns: Canonical call-argument source text.
    :raises TypeError: If the node is not a supported call-argument wrapper.

    .. note::
       Argument markers are emitted by this helper so calls preserve the
       distinction between positional, variadic, keyword, and mapping-unpack
       arguments.
    """
    if isinstance(node, LclPositionalArgument):
        return render(node.value, 0)
    if isinstance(node, LclStarArgument):
        return f"*{render(node.value, 0)}"
    if isinstance(node, LclKeywordArgument):
        return f"{node.name}={render(node.value, 0)}"
    if isinstance(node, LclKeywordUnpackArgument):
        return f"**{render(node.value, 0)}"
    raise TypeError("call contains an unsupported argument node")


def internal_index(node: LclAstNode, render: Render) -> str:
    """Render a subscript index, tuple index, or slice.

    :param node: Subscript index node to render.
    :param render: Recursive dispatcher for index expressions.
    :returns: Canonical subscript-index source text.

    .. note::
       Tuple indices are joined without an extra pair of parentheses because
       the surrounding subscript brackets already provide the grouping.
    """
    if isinstance(node, LclTuple):
        return ", ".join(render(element, 0) for element in node.elements)
    if isinstance(node, LclSlice):
        return internal_slice(node, render)
    return render(node, 0)


def internal_slice(node: LclSlice, render: Render) -> str:
    """Render a slice with its optional lower, upper, and step bounds.

    :param node: Slice node to render.
    :param render: Recursive dispatcher for present bounds.
    :returns: Canonical colon-separated slice source text.

    .. note::
       Missing bounds are represented by empty fields, while a present step
       adds the second colon required by slice syntax.
    """
    lower = "" if node.lower is None else render(node.lower, 0)
    upper = "" if node.upper is None else render(node.upper, 0)
    if node.step is None:
        return f"{lower}:{upper}"
    return f"{lower}:{upper}:{render(node.step, 0)}"
