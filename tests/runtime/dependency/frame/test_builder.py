"""Behavioural tests mirroring :mod:`pylcl.runtime.dependency.frame.builder`."""

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import (
    DependencyKind,
    Frame,
    FrameBindingKind,
    FrameDependencyBinding,
    FrameDependencyGraph,
    Module,
    build_dependency_graph,
)
from pylcl.types import FrameId, ModuleName, VarName


def module(name: str, definitions: dict[str, str]) -> Module:
    """Build one test Module from source strings."""
    return Module(
        ModuleName(name),
        {key: parse_expression(source) for key, source in definitions.items()},
    )


def binding(
    path: tuple[FrameId, ...],
    name: str,
    kind: FrameBindingKind,
) -> FrameDependencyBinding:
    """Build one expected qualified dependency binding."""
    return FrameDependencyBinding(path, VarName(name), kind)


def test_frame_graph_resolves_definitions_values_paths_and_missing_names() -> None:
    """Hierarchy lookup becomes qualified edges without executing host code."""
    calls = 0

    def explode() -> int:
        nonlocal calls
        calls += 1
        return 99

    parent = Frame(
        module(
            "parent-module",
            {
                "parent_total": "parent_base + root_value",
                "parent_base": "host_value",
                "masked": "explode()",
            },
        ),
        FrameId("parent"),
        values={"host_value": 10, "root_value": 5, "explode": explode, "masked": 4},
    )
    child = Frame(
        module(
            "child-module",
            {
                "result": "parent_total + local_value + missing",
                "masked": "1",
            },
        ),
        FrameId("child"),
        values={"local_value": 2, "masked": 3},
        parent=parent,
    )

    graph = build_dependency_graph(child)

    assert isinstance(graph, FrameDependencyGraph)
    child_path = (FrameId("child"),)
    parent_path = (FrameId("child"), FrameId("parent"))
    result = binding(child_path, "result", FrameBindingKind.DEFINITION)
    parent_total = binding(parent_path, "parent_total", FrameBindingKind.DEFINITION)
    local_value = binding(child_path, "local_value", FrameBindingKind.VALUE)
    assert graph.root == FrameId("child")
    assert graph.definitions[:3] == (
        result,
        binding(child_path, "masked", FrameBindingKind.DEFINITION),
        parent_total,
    )
    assert local_value in graph.values
    assert binding(child_path, "masked", FrameBindingKind.VALUE) not in graph.values
    assert graph.external_names == (VarName("missing"),)
    assert [edge.target for edge in graph.dependencies(result)] == [
        parent_total,
        local_value,
        None,
    ]
    assert [edge.lookup_path for edge in graph.dependencies(result)] == [
        (FrameId("child"), FrameId("parent")),
        (FrameId("child"),),
        (FrameId("child"), FrameId("parent")),
    ]
    assert tuple(graph.dependants(parent_total))[0].source == result
    assert calls == 0
    assert child.dependency_snapshot("result").dynamic_edges == ()
    assert parent.dependency_snapshot("masked").dynamic_edges == ()


def test_parent_definition_dependencies_start_lookup_at_the_parent_owner() -> None:
    """A parent AST never resolves a dependency back through its child."""
    parent = Frame(
        module("parent", {"selected": "value"}),
        FrameId("parent"),
        values={"value": 10},
    )
    child = Frame(
        module("child", {"value": "1", "result": "selected"}),
        FrameId("child"),
        parent=parent,
    )

    graph = build_dependency_graph(child)

    assert isinstance(graph, FrameDependencyGraph)
    parent_path = (FrameId("child"), FrameId("parent"))
    selected = binding(parent_path, "selected", FrameBindingKind.DEFINITION)
    edge = graph.dependencies(selected)[0]
    assert edge.target == binding(parent_path, "value", FrameBindingKind.VALUE)
    assert edge.lookup_path == (FrameId("parent"),)


def test_frame_graph_filters_kinds_and_rejects_invalid_hierarchies() -> None:
    """Queries filter statically while bad inputs and parent cycles fail early."""
    parent = Frame(module("parent", {}), FrameId("parent"))
    child = Frame(
        module("child", {"lazy": "def (): host"}),
        FrameId("child"),
        values={"host": 1},
        parent=parent,
    )
    graph = build_dependency_graph(child)
    assert isinstance(graph, FrameDependencyGraph)
    lazy = graph.definitions[0]
    assert graph.dependencies(lazy, frozenset({DependencyKind.EAGER})) == ()
    assert len(graph.dependencies(lazy, frozenset({DependencyKind.DEFERRED}))) == 1
    with pytest.raises(TypeError):
        build_dependency_graph(object())  # type: ignore[call-overload]

    parent.parent = child
    with pytest.raises(ValueError, match="cycle"):
        build_dependency_graph(child)
