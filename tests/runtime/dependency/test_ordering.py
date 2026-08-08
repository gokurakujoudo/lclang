"""Unit tests mirroring :mod:`pylcl.runtime.dependency.ordering`."""

import pytest

from pylcl.errors import LclCircularDependencyError
from pylcl.lang.parser import parse_expression
from pylcl.runtime import (
    DependencyGraph,
    DependencyKind,
    Module,
    build_dependency_graph,
    topological_order,
)
from pylcl.types import ModuleName, VarName


def _graph(**definitions: str) -> DependencyGraph:
    module = Module(
        ModuleName("app"),
        {name: parse_expression(source) for name, source in definitions.items()},
    )
    return build_dependency_graph(module)


def test_eager_order_places_local_dependencies_first_deterministically() -> None:
    """External names and repeated edges do not disturb stable local ordering."""
    graph = _graph(alpha="beta + gamma + beta", beta="gamma", gamma="external")
    assert topological_order(graph) == tuple(
        VarName(name) for name in ("gamma", "beta", "alpha")
    )


def test_empty_kind_filter_returns_definition_order() -> None:
    """Selecting no edges preserves the module's declared vertex order."""
    graph = _graph(alpha="beta", beta="alpha")
    assert topological_order(graph, kinds=frozenset()) == (
        VarName("alpha"),
        VarName("beta"),
    )


def test_unselected_conditional_cycle_does_not_block_eager_order() -> None:
    """Optional edges participate only when the caller explicitly selects them."""
    graph = _graph(alpha="beta if flag else 0", beta="alpha")
    assert topological_order(graph) == (VarName("alpha"), VarName("beta"))
    kinds = frozenset({DependencyKind.EAGER, DependencyKind.CONDITIONAL})
    with pytest.raises(LclCircularDependencyError, match="alpha -> beta -> alpha"):
        topological_order(graph, kinds=kinds)


def test_selected_cycle_reports_closing_edge_span() -> None:
    """Cycle diagnostics identify the occurrence that closes the ordered path."""
    graph = _graph(alpha="beta", beta="alpha")
    closing = next(
        edge for edge in graph.edges if edge.source == VarName("beta")
    )
    with pytest.raises(LclCircularDependencyError) as caught:
        topological_order(graph)
    assert caught.value.span == closing.span
    assert caught.value.message == "circular dependency: alpha -> beta -> alpha"


def test_self_cycle_is_reported_without_hanging() -> None:
    """A definition referencing itself produces the minimal closed path."""
    graph = _graph(value="value")
    with pytest.raises(LclCircularDependencyError, match="value -> value"):
        topological_order(graph)
