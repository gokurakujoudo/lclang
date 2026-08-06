"""Immutable module dependency graph construction and queries."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

from pylcl.errors import LclNameError
from pylcl.runtime.dependencies import DependencyEdge, DependencyKind
from pylcl.runtime.dependency_analysis import analyze_dependencies
from pylcl.runtime.modules import Module
from pylcl.types import VarName


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    """Represent ordered definitions and occurrence-preserving dependency edges.

    :param definitions: Unique non-empty local vertices in declaration order.
    :param edges: Ordered dependency occurrences owned by local definitions.
    :raises ValueError: If vertices repeat/are empty or an edge source is foreign.

    .. note::
       Targets may be external names and repeated edges are retained.
    """

    definitions: tuple[VarName, ...]
    edges: tuple[DependencyEdge, ...]

    def __post_init__(self) -> None:
        """Validate immutable graph ownership invariants."""
        local = {str(name) for name in self.definitions}
        if len(local) != len(self.definitions) or any(not name for name in local):
            raise ValueError("dependency graph definitions must be unique and non-empty")
        if any(str(edge.source) not in local for edge in self.edges):
            raise ValueError("dependency edge source must be a local definition")

    def dependencies(
        self,
        source: str,
        kinds: Set[DependencyKind] | None = None,
    ) -> tuple[DependencyEdge, ...]:
        """Return ordered outgoing edges for one local definition.

        :param source: Local definition name to query.
        :param kinds: Optional accepted dependency classifications.
        :returns: Matching occurrence edges in graph order.
        :raises LclNameError: If *source* is not a local definition.

        .. note::
           An empty kind set intentionally selects no edges.
        """
        if source not in {str(name) for name in self.definitions}:
            raise LclNameError(f"unknown graph definition: {source}")
        return tuple(
            edge
            for edge in self.edges
            if str(edge.source) == source and _matches(edge, kinds)
        )

    def dependants(
        self,
        target: str,
        kinds: Set[DependencyKind] | None = None,
    ) -> tuple[DependencyEdge, ...]:
        """Return ordered incoming edges for a local or external target.

        :param target: Referenced name to query.
        :param kinds: Optional accepted dependency classifications.
        :returns: Matching occurrence edges in graph order.

        .. note::
           An unreferenced or external name is a valid query and may return empty.
        """
        return tuple(
            edge
            for edge in self.edges
            if str(edge.target) == target and _matches(edge, kinds)
        )

    @property
    def external_names(self) -> tuple[VarName, ...]:
        """Return unique non-local targets in first-occurrence order.

        :returns: External variable names without duplicates.

        .. note::
           Classification does not affect external-name membership.
        """
        local = {str(name) for name in self.definitions}
        seen: set[str] = set()
        result: list[VarName] = []
        for edge in self.edges:
            target = str(edge.target)
            if target not in local and target not in seen:
                seen.add(target)
                result.append(edge.target)
        return tuple(result)


def build_dependency_graph(module: Module) -> DependencyGraph:
    """Analyze every module definition into one immutable graph.

    :param module: Immutable semantic definition snapshot to analyze.
    :returns: Ordered vertices and one edge per free-name occurrence.

    .. note::
       Construction is pure and does not resolve host or parent names.
    """
    definitions = tuple(VarName(name) for name in module.definitions)
    edges: list[DependencyEdge] = []
    for source, node in module.definitions.items():
        for reference in analyze_dependencies(node):
            edges.append(
                DependencyEdge(VarName(source), reference.name, reference.kind, reference.span)
            )
    return DependencyGraph(definitions, tuple(edges))


def _matches(
    edge: DependencyEdge,
    kinds: Set[DependencyKind] | None,
) -> bool:
    return kinds is None or edge.kind in kinds
