"""Canonical rendering for displays, unpacking, and comprehensions."""

from __future__ import annotations

from lclang.ast import (
    LclAstNode,
    LclDict,
    LclDictComprehension,
    LclDictUnpack,
    LclGenerator,
    LclKeyValue,
    LclList,
    LclListComprehension,
    LclSet,
    LclSetComprehension,
    LclStarred,
    LclTuple,
)
from lclang.ast.comprehensions import LclComprehensionClause
from lclang.lang.printer._types import Render, RenderResult

COLLECTION_PRECEDENCE = 100


def render_collection(node: LclAstNode, render: Render) -> RenderResult | None:
    """Render a collection display or comprehension.

    :param node: Candidate AST node.
    :param render: Recursive dispatcher for child expressions.
    :returns: Canonical source and precedence, or ``None`` for another family.

    .. note::
       Wrapper nodes are rendered only through their owning collection.
    """
    if isinstance(node, LclTuple):
        return internal_tuple(node, render), COLLECTION_PRECEDENCE
    if isinstance(node, LclList):
        return f"[{internal_sequence(node.elements, render)}]", COLLECTION_PRECEDENCE
    if isinstance(node, LclSet):
        return f"{{{internal_sequence(node.elements, render)}}}", COLLECTION_PRECEDENCE
    if isinstance(node, LclDict):
        entries = ", ".join(internal_entry(value, render) for value in node.entries)
        return f"{{{entries}}}", COLLECTION_PRECEDENCE
    if isinstance(node, LclGenerator):
        text = f"({internal_head(node.element, render)}{internal_clauses(node.clauses, render)})"
        return text, COLLECTION_PRECEDENCE
    if isinstance(node, LclListComprehension):
        text = f"[{internal_head(node.element, render)}{internal_clauses(node.clauses, render)}]"
        return text, COLLECTION_PRECEDENCE
    if isinstance(node, LclSetComprehension):
        text = f"{{{internal_head(node.element, render)}{internal_clauses(node.clauses, render)}}}"
        return text, COLLECTION_PRECEDENCE
    if isinstance(node, LclDictComprehension):
        text = f"{{{internal_entry(node.entry, render)}{internal_clauses(node.clauses, render)}}}"
        return text, COLLECTION_PRECEDENCE
    return None


def internal_tuple(node: LclTuple, render: Render) -> str:
    """Render a tuple display, including its singleton delimiter.

    :param node: Tuple node whose elements are rendered in order.
    :param render: Recursive dispatcher for child expressions.
    :returns: Canonical tuple source text.

    .. note::
       An empty tuple and a singleton tuple receive their required Python
       delimiters explicitly.
    """
    if not node.elements:
        return "()"
    values = ", ".join(internal_head(element, render) for element in node.elements)
    suffix = "," if len(node.elements) == 1 else ""
    return f"({values}{suffix})"


def internal_sequence(values: tuple[LclAstNode, ...], render: Render) -> str:
    """Render comma-separated collection elements.

    :param values: Elements to render in source order.
    :param render: Recursive dispatcher for child expressions.
    :returns: Canonical comma-separated element source text.
    """
    return ", ".join(internal_head(value, render) for value in values)


def internal_head(node: LclAstNode, render: Render) -> str:
    """Render one collection head, preserving starred unpacking.

    :param node: Element or unpacking wrapper to render.
    :param render: Recursive dispatcher for the wrapped expression.
    :returns: Canonical source text for the collection head.

    .. note::
       Starred wrappers are handled here so the owning display and
       comprehension renderers share the same unpacking rules.
    """
    if isinstance(node, LclStarred):
        return f"*{render(node.value, 0)}"
    return render(node, 0)


def internal_entry(node: LclAstNode, render: Render) -> str:
    """Render one dictionary key-value or unpacking entry.

    :param node: Dictionary entry node to render.
    :param render: Recursive dispatcher for keys, values, and unpacked maps.
    :returns: Canonical dictionary entry source text.
    :raises TypeError: If the node is not a supported dictionary entry.
    """
    if isinstance(node, LclKeyValue):
        return f"{render(node.key, 0)}: {render(node.value, 0)}"
    if isinstance(node, LclDictUnpack):
        return f"**{render(node.value, 0)}"
    raise TypeError("dictionary contains an unsupported entry node")


def internal_clauses(clauses: tuple[LclComprehensionClause, ...], render: Render) -> str:
    """Render the iteration and filter clauses of a comprehension.

    :param clauses: Comprehension clauses in their source order.
    :param render: Recursive dispatcher for iterables and filter conditions.
    :returns: Canonical source text beginning with each ``for`` clause.

    .. note::
       Multiple conditions on one clause are emitted as consecutive ``if``
       clauses, preserving the AST's occurrence order.
    """
    parts: list[str] = []
    for clause in clauses:
        parts.append(f" for {clause.target.identifier} in {render(clause.iterable, 0)}")
        parts.extend(f" if {render(condition, 0)}" for condition in clause.conditions)
    return "".join(parts)
