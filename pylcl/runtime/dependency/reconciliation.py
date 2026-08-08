"""Pure comparison of static predictions and runtime dependency evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pylcl.runtime.dependency.model import DependencyEdge, DependencyKind
from pylcl.source import SourceSpan
from pylcl.types import VarName

type _Occurrence = tuple[VarName, VarName, SourceSpan]


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


def reconcile_dependency_edges(
    static_edges: tuple[DependencyEdge, ...],
    dynamic_edges: tuple[DependencyEdge, ...],
) -> DependencyReconciliation:
    """Compare predicted and observed dependency occurrences exactly.

    :param static_edges: Ordered non-dynamic prediction occurrences.
    :param dynamic_edges: Ordered runtime observation occurrences.
    :returns: Immutable confirmed, inactive, and unexpected partitions.
    :raises ValueError: If an edge appears in the wrong classification channel.

    .. note::
       Matching uses source, target, and structural span equality; the runtime
       kind never overwrites the more specific static classification.
    """
    if any(edge.kind is DependencyKind.DYNAMIC for edge in static_edges):
        raise ValueError("static dependency edges cannot be dynamic")
    if any(edge.kind is not DependencyKind.DYNAMIC for edge in dynamic_edges):
        raise ValueError("dynamic dependency edges must use the dynamic kind")
    static_keys = {_key(edge) for edge in static_edges}
    dynamic_keys = {_key(edge) for edge in dynamic_edges}
    confirmed = tuple(edge for edge in static_edges if _key(edge) in dynamic_keys)
    inactive = tuple(edge for edge in static_edges if _key(edge) not in dynamic_keys)
    unexpected = tuple(edge for edge in dynamic_edges if _key(edge) not in static_keys)
    return DependencyReconciliation(confirmed, inactive, unexpected)


def _key(edge: DependencyEdge) -> _Occurrence:
    """Return the structural identity used for exact reconciliation.

    :param edge: Static or dynamic occurrence.
    :returns: Source, target, and span tuple independent of classification.
    """
    return edge.source, edge.target, edge.span
