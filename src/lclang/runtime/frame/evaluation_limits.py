"""Frame limits and mutable per-evaluation budget state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from lclang.errors import LclEvaluationError
from lclang.lang.evaluator.budget import internal_has_guard, internal_install_guard
from lclang.source import SourceSpan


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
        """Validate every configured ceiling.

        :raises ValueError: If a ceiling is not a positive integer.
        """
        values = (self.max_depth, self.max_steps, self.max_collection_items)
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("evaluation limits must be positive integers")


class InternalEvaluationBudget:
    """Track mutable step consumption for one evaluation chain."""

    def __init__(self, limits: EvaluationLimits) -> None:
        """Start an unused budget with immutable ceilings.

        :param limits: Ceilings applied throughout the evaluation chain.
        """
        self.limits = limits
        self.steps = 0

    def enter(self, span: SourceSpan, depth: int) -> None:
        """Charge one node visit and enforce depth and step ceilings.

        :param span: Node span used for limit diagnostics.
        :param depth: Current semantic evaluation depth.
        :raises LclEvaluationError: If depth or steps exceed their ceiling.
        """
        if depth > self.limits.max_depth:
            raise LclEvaluationError("evaluation depth limit exceeded", span=span)
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise LclEvaluationError("evaluation step limit exceeded", span=span)

    def collection(self, size: int, span: SourceSpan) -> None:
        """Enforce the materialized collection-size ceiling.

        :param size: Candidate materialized item count.
        :param span: Collection expression span used for diagnostics.
        :raises LclEvaluationError: If *size* exceeds its ceiling.
        """
        if size > self.limits.max_collection_items:
            raise LclEvaluationError("collection item limit exceeded", span=span)


@contextmanager
def internal_budget_scope(limits: EvaluationLimits) -> Generator[None]:
    """Install a budget only for the outermost Frame evaluation.

    :param limits: Ceilings used when a new guard is required.
    :returns: Context-manager iterator yielding once.
    """
    if internal_has_guard():
        yield
        return
    with internal_install_guard(InternalEvaluationBudget(limits)):
        yield
