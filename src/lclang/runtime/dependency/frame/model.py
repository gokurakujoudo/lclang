"""Immutable qualified dependency evidence for Frame hierarchies."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from enum import StrEnum

from lclang.errors import LclNameError
from lclang.runtime.dependency.model import DependencyKind
from lclang.source import SourceSpan
from lclang.types import FrameId, VarName


class FrameBindingKind(StrEnum):
    """Classify a selected Frame binding as syntax or an opaque host value.

    .. note::
       String values are stable for graph serialization and diagnostics.
    """

    # Binding backed by one immutable expression AST.
    DEFINITION = "definition"
    # Binding backed by one opaque host-supplied value.
    VALUE = "value"


@dataclass(frozen=True, slots=True)
class FrameDependencyBinding:
    """Identify one binding at an exact position in a Frame parent chain.

    :param frame_path: IDs from analyzed Frame through the binding owner.
    :param name: Non-empty selected binding name.
    :param kind: Definition or host-value classification.
    :raises ValueError: If the path/name is empty or the kind is invalid.
    .. note::
       Positional paths distinguish shadowed names without evaluating values.
    """

    frame_path: tuple[FrameId, ...]
    name: VarName
    kind: FrameBindingKind

    def __post_init__(self) -> None:
        """Validate the immutable qualified binding.

        :returns: ``None`` after successful validation.
        :raises ValueError: If the path, name, or kind is invalid.
        .. note::
           Validation uses identifiers only and never inspects a host value.
        """
        if not self.frame_path or any(not frame_id for frame_id in self.frame_path):
            raise ValueError("Frame binding path cannot be empty")
        if not self.name:
            raise ValueError("Frame binding name cannot be empty")
        if not isinstance(self.kind, FrameBindingKind):
            raise ValueError("Frame binding kind must be a FrameBindingKind")


@dataclass(frozen=True, slots=True)
class FrameDependencyEdge:
    """Resolve one static occurrence through a Frame hierarchy.

    :param source: Qualified definition containing the occurrence.
    :param target_name: Name requested by the expression.
    :param target: Selected definition/value, or ``None`` when unresolved.
    :param kind: Static evaluation classification.
    :param span: Exact requesting source occurrence.
    :param lookup_path: Frame IDs searched from the source owner outward.
    :raises ValueError: If endpoints, kinds, or paths are inconsistent.
    .. note::
       Repeated references retain separate edges and exact source spans.
    """

    source: FrameDependencyBinding
    target_name: VarName
    target: FrameDependencyBinding | None
    kind: DependencyKind
    span: SourceSpan
    lookup_path: tuple[FrameId, ...]

    def __post_init__(self) -> None:
        """Validate resolved occurrence invariants.

        :returns: ``None`` after successful validation.
        :raises ValueError: If endpoints, kinds, or paths are inconsistent.
        .. note::
           An unresolved target is valid evidence rather than an invalid edge.
        """
        if self.source.kind is not FrameBindingKind.DEFINITION:
            raise ValueError("Frame dependency source must be a definition")
        if not self.target_name:
            raise ValueError("Frame dependency target name cannot be empty")
        if self.target is not None and self.target.name != self.target_name:
            raise ValueError("resolved Frame target name must match the request")
        if not isinstance(self.kind, DependencyKind):
            raise ValueError("Frame dependency kind must be a DependencyKind")
        if not self.lookup_path or any(not frame_id for frame_id in self.lookup_path):
            raise ValueError("Frame dependency lookup path cannot be empty")


@dataclass(frozen=True, slots=True)
class FrameDependencyGraph:
    """Snapshot static lookup across one complete Frame hierarchy.

    :param root: ID of the analyzed child-most Frame.
    :param definitions: Qualified syntax vertices in child-to-parent order.
    :param values: Selectable opaque host-value terminals in the same order.
    :param edges: Occurrence-preserving resolved static dependency edges.
    :raises ValueError: If bindings repeat or edges refer outside this graph.
    .. note::
       Opaque host values are represented by bindings but are not retained.
    """

    root: FrameId
    definitions: tuple[FrameDependencyBinding, ...]
    values: tuple[FrameDependencyBinding, ...]
    edges: tuple[FrameDependencyEdge, ...]

    def __post_init__(self) -> None:
        """Validate binding uniqueness and edge ownership.

        :returns: ``None`` after successful validation.
        :raises ValueError: If roots, bindings, or edge ownership are invalid.
        .. note::
           Validation is structural and cannot invoke a definition or value.
        """
        if not self.root:
            raise ValueError("Frame dependency graph root cannot be empty")
        if len(set(self.definitions)) != len(self.definitions):
            raise ValueError("Frame dependency definitions must be unique")
        if len(set(self.values)) != len(self.values):
            raise ValueError("Frame dependency values must be unique")
        definitions = set(self.definitions)
        bindings = definitions | set(self.values)
        if any(edge.source not in definitions for edge in self.edges):
            raise ValueError("Frame dependency edge source must be a definition")
        if any(edge.target not in bindings for edge in self.edges if edge.target):
            raise ValueError("Frame dependency edge target must belong to the graph")

    def dependencies(
        self,
        source: FrameDependencyBinding,
        kinds: Set[DependencyKind] | None = None,
    ) -> tuple[FrameDependencyEdge, ...]:
        """Return ordered outgoing occurrences for one qualified definition.

        :param source: Definition binding to query.
        :param kinds: Optional accepted dependency classifications.
        :returns: Matching occurrence edges in graph order.
        :raises LclNameError: If *source* is not a graph definition.

        .. note::
           An empty kind set intentionally selects no occurrences.
        """
        if source not in self.definitions:
            raise LclNameError(f"unknown Frame graph definition: {source.name}")
        return tuple(
            edge
            for edge in self.edges
            if edge.source == source and (kinds is None or edge.kind in kinds)
        )

    def dependants(
        self,
        target: FrameDependencyBinding,
        kinds: Set[DependencyKind] | None = None,
    ) -> tuple[FrameDependencyEdge, ...]:
        """Return ordered incoming occurrences for one qualified binding.

        :param target: Definition or host-value binding to query.
        :param kinds: Optional accepted dependency classifications.
        :returns: Matching occurrence edges in graph order.

        .. note::
           Definition and value terminals use the same reverse query.
        """
        return tuple(
            edge
            for edge in self.edges
            if edge.target == target and (kinds is None or edge.kind in kinds)
        )

    @property
    def external_names(self) -> tuple[VarName, ...]:
        """Return unresolved names once in first-occurrence order.

        :returns: Names whose complete owner lookup path found no binding.
        .. note::
           Resolved host values are terminals and therefore never external.
        """
        seen: set[str] = set()
        result: list[VarName] = []
        for edge in self.edges:
            name = str(edge.target_name)
            if edge.target is None and name not in seen:
                seen.add(name)
                result.append(edge.target_name)
        return tuple(result)
