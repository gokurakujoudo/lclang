"""Immutable point-in-time dependency evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pylcl.runtime.dependencies import DependencyEdge
from pylcl.runtime.dependency_reconciliation import (
    DependencyReconciliation,
    reconcile_dependency_edges,
)
from pylcl.types import VarName


@dataclass(frozen=True, slots=True)
class DependencySnapshot:
    """Capture predicted and observed edges for one definition.

    :param source: Non-empty definition that owns all snapshot edges.
    :param static_edges: Ordered static prediction occurrences.
    :param dynamic_edges: Ordered runtime observation occurrences.
    :param reconciliation: Exact comparison of the two edge collections.
    :raises ValueError: If sources, edge channels, or reconciliation disagree.

    .. note::
       Tuples and reconciliation are immutable point-in-time evidence.
    """

    source: VarName
    static_edges: tuple[DependencyEdge, ...]
    dynamic_edges: tuple[DependencyEdge, ...]
    reconciliation: DependencyReconciliation

    def __post_init__(self) -> None:
        """Reject internally contradictory public snapshot values."""
        if not self.source:
            raise ValueError("dependency snapshot source cannot be empty")
        edges = (*self.static_edges, *self.dynamic_edges)
        if any(edge.source != self.source for edge in edges):
            raise ValueError("dependency snapshot edge source does not match")
        expected = reconcile_dependency_edges(self.static_edges, self.dynamic_edges)
        if self.reconciliation != expected:
            raise ValueError("dependency snapshot reconciliation does not match")
