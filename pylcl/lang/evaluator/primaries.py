"""Evaluation for attributes, subscriptions, and slice values."""

from __future__ import annotations

import operator
from typing import Any, cast

from pylcl.ast import (
    LclAttribute,
    LclSafeAttribute,
    LclSlice,
    LclSubscript,
)
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver

type PrimaryNode = LclAttribute | LclSafeAttribute | LclSubscript | LclSlice


async def _evaluate_primary(
    node: PrimaryNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate an attribute, safe attribute, subscript, or slice node.

    :param node: Primary-expression AST node to evaluate.
    :param resolver: Resolver supplying names referenced by child expressions.
    :param evaluate: Recursive evaluator for receivers and index expressions.
    :returns: Attribute value, indexed value, ``None`` for a safe null access,
       or a constructed :class:`slice`.

    .. note::
       Safe attributes return ``None`` without attribute lookup when their
       receiver is ``None``; ordinary attributes and subscripts propagate their
       native Python lookup behavior.
    """
    if isinstance(node, (LclAttribute, LclSafeAttribute)):
        value = await evaluate(node.value, resolver)
        if isinstance(node, LclSafeAttribute) and value is None:
            return None
        return getattr(value, str(node.name))
    if isinstance(node, LclSubscript):
        value = await evaluate(node.value, resolver)
        index = await evaluate(node.index, resolver)
        return cast(object, operator.getitem(cast(Any, value), index))
    return await _slice(node, resolver, evaluate)


async def _slice(
    node: LclSlice,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> slice:
    """Evaluate the optional bounds of a slice expression.

    :param node: Slice AST node containing optional lower, upper, and step
       expressions.
    :param resolver: Resolver supplying names referenced by bound expressions.
    :param evaluate: Recursive evaluator for each present bound.
    :returns: Python :class:`slice` value with evaluated bounds.

    .. note::
       Missing bounds remain ``None`` and are not evaluated, preserving open
       slice semantics and avoiding unnecessary resolver calls.
    """
    lower = None if node.lower is None else await evaluate(node.lower, resolver)
    upper = None if node.upper is None else await evaluate(node.upper, resolver)
    step = None if node.step is None else await evaluate(node.step, resolver)
    return slice(lower, upper, step)
