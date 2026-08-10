"""Behavioural tests for immutable LCL AST nodes."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from lclang.ast import LclAstNode, LclConstant, LclName, LclTuple, LclVisitor
from lclang.types import VarName


class TypeNameVisitor(LclVisitor[str]):
    """Return the concrete node type for delegation tests."""

    def visit(self, node: LclAstNode) -> str:
        """Return the concrete class name."""
        return type(node).__name__


def test_nodes_are_frozen_structural_values() -> None:
    """Equivalent AST nodes compare equal and cannot be mutated."""
    node = LclConstant(value=42)
    assert node == LclConstant(value=42)
    with pytest.raises(FrozenInstanceError):
        node.value = 43  # type: ignore[misc]


def test_children_and_walk_use_preorder_source_order() -> None:
    """Tree traversal must be deterministic for analysis and printing."""
    first = LclName(identifier=VarName("first"))
    second = LclConstant(value=2)
    root = LclTuple(elements=(first, second))
    assert root.children() == (first, second)
    assert tuple(root.walk()) == (root, first, second)


def test_accept_delegates_to_generic_visitor() -> None:
    """Nodes must not own evaluator-specific dispatch logic."""
    assert LclConstant(value=None).accept(TypeNameVisitor()) == "LclConstant"


def test_name_rejects_empty_identifier() -> None:
    """An AST variable reference must always contain a usable identifier."""
    with pytest.raises(ValueError):
        LclName(identifier=VarName(""))
