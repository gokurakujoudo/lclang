"""Synchronous expression parsing and evaluation convenience boundary."""

from __future__ import annotations

import asyncio

from lclang.ast import LclAstNode
from lclang.lang.evaluator.dispatch import ResolverSource, evaluate
from lclang.lang.parser import parse_expression


def evaluate_sync(node: LclAstNode | str, resolver: ResolverSource = None) -> object:
    """Evaluate one AST or source expression using a private event loop.

    :param node: Semantic AST root or LCL expression source to parse and evaluate.
    :param resolver: Optional resolver or string-keyed value mapping.
    :returns: Fully resolved immediate result value.
    :raises RuntimeError: If called while this thread has a running event loop.
    :raises LclNameError: If a mapping-backed variable is missing.
    :raises LclEvaluationError: If evaluation or an application protocol fails.

    .. note::
       Async callers must await :func:`evaluate` instead of nesting event loops.
    """
    selected = parse_expression(node) if isinstance(node, str) else node
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("evaluate_sync cannot run here; await evaluate instead")
    return asyncio.run(evaluate(selected, resolver))
