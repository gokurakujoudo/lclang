"""Evaluation for unary, binary, and chained comparison nodes."""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any

from lclang.ast import LclBinary, LclCompare, LclUnary
from lclang.ast.operators import BinaryOperator, ComparisonOperator, UnaryOperator
from lclang.lang.evaluator._types import EvaluateNode
from lclang.lang.evaluator.context import Resolver

type UnaryFunction = Callable[[Any], object]
type BinaryFunction = Callable[[Any, Any], object]
type ComparisonFunction = Callable[[Any, Any], object]
type OperationNode = LclUnary | LclBinary | LclCompare

# Unitless dispatch tables map grammar operators to Python operator functions; explicit entries
# restrict evaluation to supported operations.
_UNARY: dict[UnaryOperator, UnaryFunction] = {
    UnaryOperator.POSITIVE: operator.pos,
    UnaryOperator.NEGATIVE: operator.neg,
    UnaryOperator.INVERT: operator.invert,
}
# Unitless dispatch tables map grammar operators to Python operator functions; explicit entries
# restrict evaluation to supported operations.
_BINARY: dict[BinaryOperator, BinaryFunction] = {
    BinaryOperator.ADD: operator.add,
    BinaryOperator.SUBTRACT: operator.sub,
    BinaryOperator.MULTIPLY: operator.mul,
    BinaryOperator.MATRIX_MULTIPLY: operator.matmul,
    BinaryOperator.TRUE_DIVIDE: operator.truediv,
    BinaryOperator.FLOOR_DIVIDE: operator.floordiv,
    BinaryOperator.MODULO: operator.mod,
    BinaryOperator.POWER: operator.pow,
    BinaryOperator.LEFT_SHIFT: operator.lshift,
    BinaryOperator.RIGHT_SHIFT: operator.rshift,
    BinaryOperator.BIT_AND: operator.and_,
    BinaryOperator.BIT_XOR: operator.xor,
    BinaryOperator.BIT_OR: operator.or_,
}
# Unitless dispatch tables map grammar operators to Python operator functions; explicit entries
# restrict evaluation to supported operations.
_COMPARE: dict[ComparisonOperator, ComparisonFunction] = {
    ComparisonOperator.LESS: operator.lt,
    ComparisonOperator.LESS_EQUAL: operator.le,
    ComparisonOperator.GREATER: operator.gt,
    ComparisonOperator.GREATER_EQUAL: operator.ge,
    ComparisonOperator.EQUAL: operator.eq,
    ComparisonOperator.NOT_EQUAL: operator.ne,
    ComparisonOperator.IN: lambda left, right: operator.contains(right, left),
    ComparisonOperator.NOT_IN: lambda left, right: not operator.contains(right, left),
    ComparisonOperator.IS: operator.is_,
    ComparisonOperator.IS_NOT: operator.is_not,
}


async def internal_evaluate_operation(
    node: OperationNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a unary, binary, or comparison operation node.

    :param node: Operation AST node to evaluate.
    :param resolver: Resolver supplying names referenced by operands.
    :param evaluate: Recursive evaluator for operand expressions.
    :returns: Result produced by the selected operator implementation.

    .. note::
       Operands are evaluated left to right, and comparison nodes delegate to
       :func:`_compare` for chained-comparison semantics.
    """
    if isinstance(node, LclUnary):
        operand = await evaluate(node.operand, resolver)
        return _UNARY[node.operator](operand)
    if isinstance(node, LclBinary):
        left = await evaluate(node.left, resolver)
        right = await evaluate(node.right, resolver)
        return _BINARY[node.operator](left, right)
    return await internal_compare(node, resolver, evaluate)


async def internal_compare(
    node: LclCompare,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> bool:
    """Evaluate a chained comparison with adjacent operand reuse.

    :param node: Comparison AST node containing operators and comparator terms.
    :param resolver: Resolver supplying names referenced by operands.
    :param evaluate: Recursive evaluator for each visited operand.
    :returns: ``True`` when every comparison succeeds, otherwise ``False``.

    .. note::
       Each intermediate comparator is evaluated once and reused as the left
       operand of the next comparison; later terms are skipped after failure.
    """
    left = await evaluate(node.left, resolver)
    for comparison, comparator in zip(
        node.operators,
        node.comparators,
        strict=True,
    ):
        right = await evaluate(comparator, resolver)
        if not bool(_COMPARE[comparison](left, right)):
            return False
        left = right
    return True
