"""Frame limits and mutable per-evaluation budget state.

Defines ``EvaluationLimits``, ``InternalEvaluationBudget``, ``internal_budget_scope``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

if TYPE_CHECKING:
    pass

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from lclang.common.source_location import SourceSpan
from lclang.lang.engine.evaluator.evaluation_budget import (
    internal_has_guard,
    internal_install_guard,
)


@guard_constructor(LclValidationError, RuntimeErrorCode.E37_EVALUATION_LIMIT_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class EvaluationLimits:
    """Set resource ceilings for one uncached Frame evaluation chain.

    :param max_depth: Maximum simultaneously nested semantic AST nodes.
    :param max_steps: Maximum semantic AST node visits in the chain.
    :param max_collection_items: Maximum items in one materialized collection.
    :raises LclValidationError: If any limit is boolean, non-integer, or not positive.

    .. note::
       Cached lookup consumes no budget; recalculation starts a fresh budget.
    """

    max_depth: int = 100
    max_steps: int = 100_000
    max_collection_items: int = 10_000

    @guard_failure(LclValidationError, RuntimeErrorCode.E37_EVALUATION_LIMIT_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate every configured ceiling.

        :raises LclValidationError: If a ceiling is not a positive integer.
        """
        values = (self.max_depth, self.max_steps, self.max_collection_items)
        if any(type(value) is not int or value <= 0 for value in values):
            raise LclValidationError(
                "evaluation limits must be positive integers",
                code=RuntimeErrorCode.E37_EVALUATION_LIMITS_MUST_BE_POSITIVE_INTEGERS,
            )


@guard_constructor(LclValidationError, RuntimeErrorCode.E37_EVALUATION_LIMIT_NATIVE_FAILURE)
class InternalEvaluationBudget:
    """Track mutable step consumption for one evaluation chain."""

    def __init__(self, limits: EvaluationLimits) -> None:
        """Start an unused budget with immutable ceilings.

        :param limits: Ceilings applied throughout the evaluation chain.
        """
        self.limits = limits
        self.steps = 0

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E37_EVALUATION_LIMIT_NATIVE_FAILURE)
    def enter(self, span: SourceSpan, depth: int) -> None:
        """Charge one node visit and enforce depth and step ceilings.

        :param span: Node span used for limit diagnostics.
        :param depth: Current semantic evaluation depth.
        :raises LclEvaluationError: If depth or steps exceed their ceiling.
        """
        if depth > self.limits.max_depth:
            raise LclEvaluationError(
                "evaluation depth limit exceeded",
                span=span,
                code=RuntimeErrorCode.E37_EVALUATION_DEPTH_LIMIT_EXCEEDED,
            )
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise LclEvaluationError(
                "evaluation step limit exceeded",
                span=span,
                code=RuntimeErrorCode.E37_EVALUATION_STEP_LIMIT_EXCEEDED,
            )

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E37_EVALUATION_LIMIT_NATIVE_FAILURE)
    def collection(self, size: int, span: SourceSpan) -> None:
        """Enforce the materialized collection-size ceiling.

        :param size: Candidate materialized item count.
        :param span: Collection expression span used for diagnostics.
        :raises LclEvaluationError: If *size* exceeds its ceiling.
        """
        if size > self.limits.max_collection_items:
            raise LclEvaluationError(
                "collection item limit exceeded",
                span=span,
                code=RuntimeErrorCode.E37_COLLECTION_ITEM_LIMIT_EXCEEDED,
            )


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
