"""Precedence-aware rendering for operator expression nodes."""

from __future__ import annotations

from lclang.ast import (
    LclAstNode,
    LclBinary,
    LclBoolean,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclUnary,
)
from lclang.ast.operators import BinaryOperator, BooleanOperator, UnaryOperator
from lclang.lang.printer._types import Render, RenderResult

_BINARY_PRECEDENCE = {
    BinaryOperator.BIT_OR: 50,
    BinaryOperator.BIT_XOR: 55,
    BinaryOperator.BIT_AND: 60,
    BinaryOperator.LEFT_SHIFT: 65,
    BinaryOperator.RIGHT_SHIFT: 65,
    BinaryOperator.ADD: 70,
    BinaryOperator.SUBTRACT: 70,
    BinaryOperator.MULTIPLY: 75,
    BinaryOperator.MATRIX_MULTIPLY: 75,
    BinaryOperator.TRUE_DIVIDE: 75,
    BinaryOperator.FLOOR_DIVIDE: 75,
    BinaryOperator.MODULO: 75,
    BinaryOperator.POWER: 85,
}


def render_expression(node: LclAstNode, render: Render) -> RenderResult | None:
    """Render one ordinary operator expression.

    :param node: Candidate AST node.
    :param render: Recursive dispatcher applying parent precedence.
    :returns: Canonical source and precedence, or ``None`` for another family.

    .. note::
       Side-specific precedence preserves associativity with minimal parentheses.
    """
    if isinstance(node, LclUnary):
        return internal_unary(node, render)
    if isinstance(node, LclBinary):
        return internal_binary(node, render)
    if isinstance(node, LclCompare):
        pieces = [render(node.left, 46)]
        for operator, comparator in zip(node.operators, node.comparators, strict=True):
            pieces.extend((operator.value, render(comparator, 46)))
        return " ".join(pieces), 45
    if isinstance(node, LclBoolean):
        precedence = 35 if node.operator is BooleanOperator.AND else 30
        separator = f" {node.operator.value} "
        return separator.join(render(value, precedence) for value in node.values), precedence
    if isinstance(node, LclCoalesce):
        return f"{render(node.left, 21)} ?? {render(node.right, 20)}", 20
    if isinstance(node, LclConditional):
        text = (
            f"{render(node.when_true, 11)} if {render(node.condition, 11)} "
            f"else {render(node.when_false, 10)}"
        )
        return text, 10
    return None


def internal_unary(node: LclUnary, render: Render) -> RenderResult:
    """Render a unary operator with its operand precedence.

    :param node: Unary expression node to render.
    :param render: Recursive dispatcher applying the operand precedence.
    :returns: Canonical unary-expression source and its precedence.

    .. note::
       ``not`` uses its lower logical precedence, while symbolic unary
       operators use the higher arithmetic precedence.
    """
    if node.operator is UnaryOperator.NOT:
        return f"not {render(node.operand, 40)}", 40
    return f"{node.operator.value}{render(node.operand, 80)}", 80


def internal_binary(node: LclBinary, render: Render) -> RenderResult:
    """Render a binary operator while preserving associativity.

    :param node: Binary expression node to render.
    :param render: Recursive dispatcher applying child-specific precedence.
    :returns: Canonical binary-expression source and its precedence.

    .. note::
       Exponentiation is right-associative, so its left and right operands
       receive different precedence thresholds from the other operators.
    """
    precedence = _BINARY_PRECEDENCE[node.operator]
    if node.operator is BinaryOperator.POWER:
        left = render(node.left, precedence + 1)
        right = render(node.right, 80)
    else:
        left = render(node.left, precedence)
        right = render(node.right, precedence + 1)
    return f"{left} {node.operator.value} {right}", precedence
