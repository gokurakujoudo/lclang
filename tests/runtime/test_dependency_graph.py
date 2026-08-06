"""Unit tests mirroring :mod:`pylcl.runtime.dependency_graph`."""

import pytest

from pylcl.errors import LclNameError
from pylcl.lang.parser import parse_expression
from pylcl.runtime import (
    DependencyGraph,
    DependencyKind,
    Module,
    build_dependency_graph,
)
from pylcl.types import ModuleName, VarName


def _module() -> Module:
    return Module(
        ModuleName("app"),
        {
            "alpha": parse_expression("beta + external + beta"),
            "lazy": parse_expression("def (): alpha + later"),
            "beta": parse_expression("1"),
        },
    )


def _edges(graph: DependencyGraph) -> list[tuple[str, str, DependencyKind]]:
    return [
        (str(edge.source), str(edge.target), edge.kind)
        for edge in graph.edges
    ]


def test_build_preserves_definition_and_occurrence_order() -> None:
    """Vertices follow module order and repeated references remain explicit."""
    graph = build_dependency_graph(_module())
    assert graph.definitions == tuple(VarName(name) for name in ("alpha", "lazy", "beta"))
    assert _edges(graph) == [
        ("alpha", "beta", DependencyKind.EAGER),
        ("alpha", "external", DependencyKind.EAGER),
        ("alpha", "beta", DependencyKind.EAGER),
        ("lazy", "alpha", DependencyKind.DEFERRED),
        ("lazy", "later", DependencyKind.DEFERRED),
    ]


def test_forward_and_reverse_queries_filter_without_deduplication() -> None:
    """Queries retain evidence multiplicity and accept immutable kind filters."""
    graph = build_dependency_graph(_module())
    assert len(graph.dependencies("alpha")) == 3
    assert len(graph.dependants("beta")) == 2
    assert graph.dependencies("lazy", frozenset({DependencyKind.EAGER})) == ()
    deferred = graph.dependencies("lazy", frozenset({DependencyKind.DEFERRED}))
    assert tuple(str(edge.target) for edge in deferred) == ("alpha", "later")
    with pytest.raises(LclNameError):
        graph.dependencies("missing")


def test_external_names_are_unique_in_first_occurrence_order() -> None:
    """References outside module vertices form a deterministic public summary."""
    graph = build_dependency_graph(_module())
    assert graph.external_names == (VarName("external"), VarName("later"))
    assert graph.dependants("unreferenced") == ()


def test_graph_constructor_rejects_duplicate_vertices_or_foreign_sources() -> None:
    """Manually constructed immutable graphs retain module ownership invariants."""
    graph = build_dependency_graph(_module())
    with pytest.raises(ValueError):
        DependencyGraph((VarName("alpha"), VarName("alpha")), ())
    foreign = graph.edges[0]
    invalid = type(foreign)(VarName("missing"), foreign.target, foreign.kind, foreign.span)
    with pytest.raises(ValueError):
        DependencyGraph((VarName("alpha"),), (invalid,))
