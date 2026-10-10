"""Pure comparison of static predictions and runtime dependency evidence.

Defines ``DependencyReconciliation``, ``reconcile_dependency_edges``, ``internal_key``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceSpan
from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.runtime.dependency.dependency_types import DependencyEdge, DependencyKind

type _Occurrence = tuple[VarName, VarName, SourceSpan]


@guard_constructor(
    LclValidationError, RuntimeErrorCode.E45_DEPENDENCY_RECONCILIATION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class DependencyReconciliation:
    """Partition static predictions against runtime observations.

    :param confirmed: Static occurrences that runtime evaluation observed.
    :param inactive: Static occurrences not yet observed at runtime.
    :param unexpected: Runtime occurrences absent from static predictions.

    .. note::
       Static edges retain their original eager, conditional, or deferred kind.
    """

    confirmed: tuple[DependencyEdge, ...]
    inactive: tuple[DependencyEdge, ...]
    unexpected: tuple[DependencyEdge, ...]


@guard_failure(LclEvaluationError, RuntimeErrorCode.E45_DEPENDENCY_RECONCILIATION_NATIVE_FAILURE)
def reconcile_dependency_edges(
    static_edges: tuple[DependencyEdge, ...],
    dynamic_edges: tuple[DependencyEdge, ...],
) -> DependencyReconciliation:
    """Compare predicted and observed dependency occurrences exactly.

    :param static_edges: Ordered non-dynamic prediction occurrences.
    :param dynamic_edges: Ordered runtime observation occurrences.
    :returns: Immutable confirmed, inactive, and unexpected partitions.
    :raises LclValidationError: If an edge appears in the wrong classification channel.

    .. note::
       Matching uses source, target, and structural span equality; the runtime
       kind never overwrites the more specific static classification.
    """
    if any(edge.kind is DependencyKind.DYNAMIC for edge in static_edges):
        raise LclValidationError(
            "static dependency edges cannot be dynamic",
            code=RuntimeErrorCode.E45_STATIC_DEPENDENCY_EDGES_CANNOT_BE_DYNAMIC,
        )
    if any(edge.kind is not DependencyKind.DYNAMIC for edge in dynamic_edges):
        raise LclValidationError(
            "dynamic dependency edges must use the dynamic kind",
            code=RuntimeErrorCode.E45_DYNAMIC_DEPENDENCY_EDGES_MUST_USE_THE_DYNAMIC_KIND,
        )
    static_keys = {internal_key(edge) for edge in static_edges}
    dynamic_keys = {internal_key(edge) for edge in dynamic_edges}
    confirmed = tuple(edge for edge in static_edges if internal_key(edge) in dynamic_keys)
    inactive = tuple(edge for edge in static_edges if internal_key(edge) not in dynamic_keys)
    unexpected = tuple(edge for edge in dynamic_edges if internal_key(edge) not in static_keys)
    return DependencyReconciliation(confirmed, inactive, unexpected)


def internal_key(edge: DependencyEdge) -> _Occurrence:
    """Return the structural identity used for exact reconciliation.

    :param edge: Static or dynamic occurrence.
    :returns: Source, target, and span tuple independent of classification.
    """
    return edge.source, edge.target, edge.span
