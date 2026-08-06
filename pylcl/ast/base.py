"""Shared immutable AST behaviour and visitor contracts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pylcl.source import UNKNOWN_SPAN, SourceSpan

ResultT_co = TypeVar("ResultT_co", covariant=True)


class LclVisitor(Protocol[ResultT_co]):
    """Visit an AST node without coupling nodes to an interpreter.

    .. note::
       Implementations choose the result type and may maintain traversal state.
    """

    def visit(self, node: LclAstNode) -> ResultT_co:
        """Return a visitor-specific result for *node*.

        :param node: AST node supplied by :meth:`LclAstNode.accept`.
        :returns: Result selected by the concrete visitor.

        .. note::
           Child traversal is controlled by the visitor implementation.
        """
        ...


@dataclass(frozen=True, slots=True)
class LclAstNode:
    """Base value for every LCL abstract-syntax-tree node.

    :param span: Half-open location of the node in its source text.

    .. note::
       Nodes are frozen structural values; source-less nodes use ``UNKNOWN_SPAN``.
    """

    span: SourceSpan = field(default=UNKNOWN_SPAN, kw_only=True)

    def children(self) -> tuple[LclAstNode, ...]:
        """Return direct child nodes in source order.

        :returns: An empty tuple for a leaf node.

        .. note::
           Subclasses override this method only for structural AST children.
        """
        return ()

    def walk(self) -> Iterator[LclAstNode]:
        """Yield this node and its descendants in preorder.

        :returns: A lazy preorder iterator beginning with this node.

        .. note::
           Sibling order always matches :meth:`children`.
        """
        yield self
        for child in self.children():
            yield from child.walk()

    def accept(self, visitor: LclVisitor[ResultT_co]) -> ResultT_co:
        """Delegate this node to a generic visitor.

        :param visitor: Visitor receiving this exact node.
        :returns: The visitor's result without transformation.

        .. note::
           This method does not automatically visit child nodes.
        """
        return visitor.visit(self)
