"""Immutable module dependency graph construction and queries."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from pylcl.errors import LclNameError
from pylcl.runtime.dependency.analysis import analyze_dependencies
from pylcl.runtime.dependency.model import DependencyEdge, DependencyKind
from pylcl.runtime.modules import Module
from pylcl.types import VarName

if TYPE_CHECKING:
    from pylcl.runtime.dependency.frame.model import FrameDependencyGraph
    from pylcl.runtime.frame import Frame


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
        """Validate immutable graph ownership invariants.

        :raises ValueError: If definitions repeat/are empty or an edge is foreign.
        """
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


@overload
def build_dependency_graph(source: Module) -> DependencyGraph:  # noqa: D418
    """Describe the name-only Module overload.

    :param source: Immutable Module definition snapshot.
    :returns: Occurrence-preserving unqualified dependency graph.

    .. note::
       This overload retains the original public Module behavior.
    """
    ...


@overload
def build_dependency_graph(source: Frame) -> FrameDependencyGraph:  # noqa: D418
    """Describe the hierarchy-aware Frame overload.

    :param source: Child-most Frame to inspect structurally.
    :returns: Qualified definitions, values, paths, and resolved edges.

    .. note::
       Type selection changes graph shape but never triggers evaluation.
    """
    ...


def build_dependency_graph(source: Module | Frame) -> DependencyGraph | FrameDependencyGraph:
    """Analyze a Module or resolve a complete Frame hierarchy graph.

    :param source: Immutable Module or runtime Frame to inspect without evaluation.
    :returns: Name-only Module graph or qualified Frame dependency graph.
    :raises TypeError: If *source* is neither a Module nor a Frame.

    .. note::
       Frame construction snapshots syntax, value names, and lookup paths only.
    """
    if isinstance(source, Module):
        return build_module_dependency_graph(source)
    from pylcl.runtime.frame import Frame

    if isinstance(source, Frame):
        from pylcl.runtime.dependency.frame.builder import build_frame_dependency_graph

        return build_frame_dependency_graph(source)
    raise TypeError("dependency graph source must be a Module or Frame")


def build_module_dependency_graph(module: Module) -> DependencyGraph:
    """Analyze every Module definition into one immutable graph.

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
    """Return whether one edge passes an optional kind filter.

    :param edge: Dependency occurrence being considered.
    :param kinds: Accepted kinds, or ``None`` to accept every kind.
    :returns: Whether the occurrence is selected.
    """
    return kinds is None or edge.kind in kinds
