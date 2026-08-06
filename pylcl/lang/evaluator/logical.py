"""Short-circuit evaluation for truth-based and null-based expressions."""

from __future__ import annotations

from pylcl.ast import (
    LclBoolean,
    LclCoalesce,
    LclConditional,
    LclUnary,
)
from pylcl.ast.operators import BooleanOperator
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver

type LogicalNode = LclUnary | LclBoolean | LclConditional | LclCoalesce


async def _evaluate_logical(
    node: LogicalNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate one unary, boolean, conditional, or coalescing expression.

    :param node: Logical AST node to evaluate.
    :param resolver: Resolver supplying names referenced by operands.
    :param evaluate: Recursive evaluator for selected child expressions.
    :returns: The logical result, preserving the selected operand value.

    .. note::
       Only the operand or branch required by the logical operation is
       evaluated, preserving short-circuit behavior and side-effect boundaries.
    """
    if isinstance(node, LclUnary):
        return not bool(await evaluate(node.operand, resolver))
    if isinstance(node, LclBoolean):
        return await _boolean(node, resolver, evaluate)
    if isinstance(node, LclConditional):
        condition = await evaluate(node.condition, resolver)
        branch = node.when_true if bool(condition) else node.when_false
        return await evaluate(branch, resolver)
    left = await evaluate(node.left, resolver)
    if left is not None:
        return left
    return await evaluate(node.right, resolver)


async def _boolean(
    node: LclBoolean,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a chained ``and`` or ``or`` expression left to right.

    :param node: Boolean AST node containing ordered operand expressions.
    :param resolver: Resolver supplying names referenced by operands.
    :param evaluate: Recursive evaluator for each visited operand.
    :returns: The first short-circuiting operand, or the final operand value.

    .. note::
       The operation returns operand values rather than coercing the result to
       ``bool``, matching Python-style truth-value semantics.
    """
    result = await evaluate(node.values[0], resolver)
    for value in node.values[1:]:
        if node.operator is BooleanOperator.AND and not bool(result):
            return result
        if node.operator is BooleanOperator.OR and bool(result):
            return result
        result = await evaluate(value, resolver)
    return result
