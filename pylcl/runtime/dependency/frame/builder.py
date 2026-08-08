"""Pure Frame hierarchy dependency graph construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylcl.ast import LclAstNode
from pylcl.runtime.dependency.analysis import analyze_dependencies
from pylcl.runtime.dependency.frame.model import (
    FrameBindingKind,
    FrameDependencyBinding,
    FrameDependencyEdge,
    FrameDependencyGraph,
)
from pylcl.runtime.dependency.frame.resolution import (
    GraphFrame,
    collect_frames,
    resolve_frame_binding,
)
from pylcl.types import VarName

if TYPE_CHECKING:
    from pylcl.runtime.frame import Frame


def build_frame_dependency_graph(frame: Frame) -> FrameDependencyGraph:
    """Build qualified static dependencies for a complete Frame chain.

    :param frame: Child-most Frame whose hierarchy should be analyzed.
    :returns: Immutable definitions, values, lookup paths, and resolved edges.
    :raises ValueError: If the mutable parent object graph contains a cycle.

    .. note::
       Construction reads names and ASTs only; opaque values are never touched.
    """
    frames = collect_frames(frame)
    paths = tuple(
        tuple(item.frame_id for item in frames[: index + 1])
        for index in range(len(frames))
    )
    definitions: list[FrameDependencyBinding] = []
    values: list[FrameDependencyBinding] = []
    definition_map: dict[tuple[int, str], FrameDependencyBinding] = {}
    value_map: dict[tuple[int, str], FrameDependencyBinding] = {}
    for index, item in enumerate(frames):
        for name in item.module.definitions:
            selected = FrameDependencyBinding(
                paths[index], VarName(name), FrameBindingKind.DEFINITION
            )
            definitions.append(selected)
            definition_map[(index, name)] = selected
        for name in item.values:
            if name not in item.module.definitions:
                selected = FrameDependencyBinding(
                    paths[index], VarName(name), FrameBindingKind.VALUE
                )
                values.append(selected)
                value_map[(index, name)] = selected
    edges = build_frame_edges(frames, definitions, definition_map, value_map)
    return FrameDependencyGraph(
        frames[0].frame_id,
        tuple(definitions),
        tuple(values),
        edges,
    )


def build_frame_edges(
    frames: tuple[GraphFrame, ...],
    definitions: list[FrameDependencyBinding],
    definition_map: dict[tuple[int, str], FrameDependencyBinding],
    value_map: dict[tuple[int, str], FrameDependencyBinding],
) -> tuple[FrameDependencyEdge, ...]:
    """Resolve every static occurrence from its defining owner.

    :param frames: Complete child-to-parent hierarchy.
    :param definitions: Qualified definitions in matching hierarchy order.
    :param definition_map: Owner-index/name definition lookup.
    :param value_map: Owner-index/name host-value lookup.
    :returns: Occurrence-preserving resolved Frame dependency edges.

    .. note::
       Each parent definition starts lookup at its own hierarchy index.
    """
    edges: list[FrameDependencyEdge] = []
    definition_index = 0
    for owner_index, frame in enumerate(frames):
        for node in frame.module.definitions.values():
            source = definitions[definition_index]
            definition_index += 1
            edges.extend(
                edges_for_node(
                    frames,
                    owner_index,
                    source,
                    node,
                    definition_map,
                    value_map,
                )
            )
    return tuple(edges)


def edges_for_node(
    frames: tuple[GraphFrame, ...],
    owner_index: int,
    source: FrameDependencyBinding,
    node: LclAstNode,
    definition_map: dict[tuple[int, str], FrameDependencyBinding],
    value_map: dict[tuple[int, str], FrameDependencyBinding],
) -> tuple[FrameDependencyEdge, ...]:
    """Resolve one definition's free-name occurrences.

    :param frames: Complete child-to-parent hierarchy.
    :param owner_index: Index where definition evaluation starts lookup.
    :param source: Qualified definition owning every returned edge.
    :param node: Immutable definition syntax to analyze.
    :param definition_map: Owner-index/name definition lookup.
    :param value_map: Owner-index/name host-value lookup.
    :returns: Ordered resolved edges for *node*.

    .. note::
       Static analysis preserves lazy and conditional dependency kinds.
    """
    result: list[FrameDependencyEdge] = []
    for reference in analyze_dependencies(node):
        target, lookup_path = resolve_frame_binding(
            frames,
            owner_index,
            str(reference.name),
            definition_map,
            value_map,
        )
        result.append(
            FrameDependencyEdge(
                source,
                reference.name,
                target,
                reference.kind,
                reference.span,
                lookup_path,
            )
        )
    return tuple(result)
