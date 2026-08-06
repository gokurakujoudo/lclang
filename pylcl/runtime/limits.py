"""Public Frame limits and mutable per-evaluation budget state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from pylcl.errors import LclEvaluationError
from pylcl.lang.evaluator.budget import _has_guard, _install_guard
from pylcl.source import SourceSpan


@dataclass(frozen=True, slots=True)
class EvaluationLimits:
    """Set resource ceilings for one uncached Frame evaluation chain.

    :param max_depth: Maximum simultaneously nested semantic AST nodes.
    :param max_steps: Maximum semantic AST node visits in the chain.
    :param max_collection_items: Maximum items in one materialized collection.
    :raises ValueError: If any limit is boolean, non-integer, or not positive.

    .. note::
       Cached lookup consumes no budget; recalculation starts a fresh budget.
    """

    max_depth: int = 100
    max_steps: int = 100_000
    max_collection_items: int = 10_000

    def __post_init__(self) -> None:
        """Validate every configured ceiling."""
        values = (self.max_depth, self.max_steps, self.max_collection_items)
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("evaluation limits must be positive integers")


class _EvaluationBudget:
    def __init__(self, limits: EvaluationLimits) -> None:
        self.limits = limits
        self.steps = 0

    def enter(self, span: SourceSpan, depth: int) -> None:
        if depth > self.limits.max_depth:
            raise LclEvaluationError("evaluation depth limit exceeded", span=span)
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise LclEvaluationError("evaluation step limit exceeded", span=span)

    def collection(self, size: int, span: SourceSpan) -> None:
        if size > self.limits.max_collection_items:
            raise LclEvaluationError("collection item limit exceeded", span=span)


@contextmanager
def _budget_scope(limits: EvaluationLimits) -> Iterator[None]:
    if _has_guard():
        yield
        return
    with _install_guard(_EvaluationBudget(limits)):
        yield
