"""Large deterministic dependency and Frame graph stress tests."""

from __future__ import annotations

import pytest

import lclang
from lclang.errors import LclCircularDependencyError
from lclang.runtime import build_dependency_graph, topological_order


def test_ten_thousand_vertex_dag_has_stable_edges_and_order() -> None:
    """A broad occurrence-heavy DAG builds and orders deterministically."""
    size = 10_000
    definitions = {
        f"n{index}": (
            "0"
            if index < 5
            else " + ".join(f"n{dependency}" for dependency in range(index - 5, index))
        )
        for index in range(size)
    }
    graph = build_dependency_graph(lclang.define_module("large-dag", definitions))
    order = topological_order(graph)
    assert len(graph.definitions) == size
    assert len(graph.edges) == (size - 5) * 5
    assert (str(order[0]), str(order[-1]), len(set(order))) == ("n0", "n9999", size)


def test_ten_thousand_vertex_cycle_is_structured_not_recursive() -> None:
    """A deep ring reports the deterministic graph error category."""
    size = 10_000
    definitions = {f"n{index}": f"n{(index + 1) % size}" for index in range(size)}
    graph = build_dependency_graph(lclang.define_module("large-cycle", definitions))
    with pytest.raises(LclCircularDependencyError) as raised:
        topological_order(graph)
    message = str(raised.value)
    assert "circular dependency: n0 -> n1 -> n2" in message
    assert message.endswith("n9999 -> n0")


def test_thousand_frame_graph_resolves_root_value_without_evaluation() -> None:
    """Qualified paths scale while opaque host values remain untouched."""
    calls = 0

    def danger() -> int:
        """Record a forbidden graph-construction invocation."""
        nonlocal calls
        calls += 1
        return 1

    root_module = lclang.define_module("layer0", {"node0": "danger"})
    root = lclang.Frame(root_module, "f0", values={"danger": danger})
    child = root
    for index in range(1, 1_000):
        module = lclang.define_module(f"layer{index}", {f"node{index}": "danger"})
        child = lclang.Frame(module, f"f{index}", parent=child)
    graph = build_dependency_graph(child)
    assert len(graph.definitions) == 1_000
    assert len(graph.values) == 1
    assert len(graph.edges) == 1_000
    assert max(len(edge.lookup_path) for edge in graph.edges) == 1_000
    assert calls == 0
