"""Immutable point-in-time dependency evidence.

Defines ``DependencySnapshot``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.error import RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.runtime.dependency.dependency_reconciliation import (
    DependencyReconciliation,
    reconcile_dependency_edges,
)
from lclang.lang.runtime.dependency.dependency_types import DependencyEdge


@guard_constructor(LclValidationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class DependencySnapshot:
    """Capture predicted and observed edges for one definition.

    :param source: Non-empty definition that owns all snapshot edges.
    :param static_edges: Ordered static prediction occurrences.
    :param dynamic_edges: Ordered runtime observation occurrences.
    :param reconciliation: Exact comparison of the two edge collections.
    :raises LclValidationError: If sources, edge channels, or reconciliation disagree.

    .. note::
       Tuples and reconciliation are immutable point-in-time evidence.
    """

    source: VarName
    static_edges: tuple[DependencyEdge, ...]
    dynamic_edges: tuple[DependencyEdge, ...]
    reconciliation: DependencyReconciliation

    @guard_failure(LclValidationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Reject internally contradictory public snapshot values.

        :raises LclValidationError: If names, edge channels, or reconciliation disagree.
        """
        if not self.source:
            raise LclValidationError(
                "dependency snapshot source cannot be empty",
                code=RuntimeErrorCode.E41_DEPENDENCY_SNAPSHOT_SOURCE_CANNOT_BE_EMPTY,
            )
        edges = (*self.static_edges, *self.dynamic_edges)
        if any(edge.source != self.source for edge in edges):
            raise LclValidationError(
                "dependency snapshot edge source does not match",
                code=RuntimeErrorCode.E41_DEPENDENCY_SNAPSHOT_EDGE_SOURCE_DOES_NOT_MATCH,
            )
        expected = reconcile_dependency_edges(self.static_edges, self.dynamic_edges)
        if self.reconciliation != expected:
            raise LclValidationError(
                "dependency snapshot reconciliation does not match",
                code=RuntimeErrorCode.E41_DEPENDENCY_SNAPSHOT_RECONCILIATION_DOES_NOT_MATCH,
            )
