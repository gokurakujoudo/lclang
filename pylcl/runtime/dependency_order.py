"""Deterministic kind-filtered dependency graph ordering."""

from __future__ import annotations

from collections.abc import Set
from typing import cast

from pylcl.errors import LclCircularDependencyError
from pylcl.runtime.dependencies import DependencyEdge, DependencyKind
from pylcl.runtime.dependency_graph import DependencyGraph
from pylcl.types import VarName

_EAGER_ONLY = frozenset({DependencyKind.EAGER})


def topological_order(
    graph: DependencyGraph,
    *,
    kinds: Set[DependencyKind] = _EAGER_ONLY,
) -> tuple[VarName, ...]:
    """Return definitions with selected local dependencies before dependants.

    :param graph: Immutable dependency graph to order.
    :param kinds: Edge classifications that constrain ordering.
    :returns: Every local definition exactly once in deterministic order.
    :raises LclCircularDependencyError: If selected local edges contain a cycle.

    .. note::
       External targets and unselected edges never constrain the result.
    """
    local = {str(name) for name in graph.definitions}
    selected = tuple(
        edge
        for edge in graph.edges
        if edge.kind in kinds and str(edge.target) in local
    )
    remaining = {str(name): 0 for name in graph.definitions}
    reverse: dict[str, list[str]] = {str(name): [] for name in graph.definitions}
    for edge in selected:
        source = str(edge.source)
        target = str(edge.target)
        remaining[source] += 1
        reverse[target].append(source)
    ready = [str(name) for name in graph.definitions if remaining[str(name)] == 0]
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for dependant in reverse[current]:
            remaining[dependant] -= 1
            if remaining[dependant] == 0:
                ready.append(dependant)
    if len(ordered) != len(graph.definitions):
        cycle = cast(tuple[str, ...], _find_cycle(graph, selected))
        closing = _closing_edge(selected, cycle)
        message = f"circular dependency: {' -> '.join(cycle)}"
        raise LclCircularDependencyError(message, span=closing.span)
    return tuple(VarName(name) for name in ordered)


def _find_cycle(
    graph: DependencyGraph,
    edges: tuple[DependencyEdge, ...],
) -> tuple[str, ...] | None:
    adjacency: dict[str, list[str]] = {str(name): [] for name in graph.definitions}
    for edge in edges:
        adjacency[str(edge.source)].append(str(edge.target))
    state = {name: 0 for name in adjacency}
    stack: list[str] = []

    def visit(name: str) -> tuple[str, ...] | None:
        state[name] = 1
        stack.append(name)
        for target in adjacency[name]:
            if state[target] == 0:
                found = visit(target)
                if found is not None:
                    return found
            elif state[target] == 1:
                start = stack.index(target)
                return (*stack[start:], target)
        stack.pop()
        state[name] = 2
        return None

    for name in adjacency:
        if state[name] == 0:
            found = visit(name)
            if found is not None:
                return found
    return None


def _closing_edge(
    edges: tuple[DependencyEdge, ...],
    cycle: tuple[str, ...],
) -> DependencyEdge:
    source, target = cycle[-2:]
    return next(
        edge
        for edge in edges
        if str(edge.source) == source and str(edge.target) == target
    )
