"""Unit tests mirroring :mod:`lclang.runtime.dependency.frame.model`."""

import pytest

from lclang.errors import LclNameError
from lclang.runtime import (
    DependencyKind,
    FrameBindingKind,
    FrameDependencyBinding,
    FrameDependencyEdge,
    FrameDependencyGraph,
)
from lclang.source import UNKNOWN_SPAN
from lclang.types import FrameId, VarName


def binding(
    name: str = "source",
    *,
    path: tuple[FrameId, ...] = (FrameId("child"),),
    kind: FrameBindingKind = FrameBindingKind.DEFINITION,
) -> FrameDependencyBinding:
    """Build one qualified binding for compact invariant tests."""
    return FrameDependencyBinding(path, VarName(name), kind)


def dependency_edge(
    source: FrameDependencyBinding,
    *,
    target_name: str = "target",
    target: FrameDependencyBinding | None = None,
    kind: DependencyKind = DependencyKind.EAGER,
    lookup_path: tuple[FrameId, ...] = (FrameId("child"),),
) -> FrameDependencyEdge:
    """Build one occurrence edge for compact invariant tests."""
    return FrameDependencyEdge(
        source,
        VarName(target_name),
        target,
        kind,
        UNKNOWN_SPAN,
        lookup_path,
    )


@pytest.mark.parametrize(
    ("path", "name", "kind"),
    [
        ((), "source", FrameBindingKind.DEFINITION),
        ((FrameId(""),), "source", FrameBindingKind.DEFINITION),
        ((FrameId("child"),), "", FrameBindingKind.DEFINITION),
        ((FrameId("child"),), "source", object()),
    ],
)
def test_binding_rejects_invalid_qualifiers(
    path: tuple[FrameId, ...],
    name: str,
    kind: object,
) -> None:
    """A binding requires a non-empty path, name, and public kind."""
    with pytest.raises(ValueError):
        FrameDependencyBinding(path, VarName(name), kind)  # type: ignore[arg-type]


def test_edge_rejects_a_value_source() -> None:
    """Only expression definitions can own dependency occurrences."""
    with pytest.raises(ValueError, match="source must be a definition"):
        dependency_edge(binding(kind=FrameBindingKind.VALUE))


def test_edge_rejects_an_empty_target_name() -> None:
    """Each occurrence retains a non-empty requested name."""
    with pytest.raises(ValueError, match="target name cannot be empty"):
        dependency_edge(binding(), target_name="")


def test_edge_rejects_a_mismatched_resolved_name() -> None:
    """A resolved binding must answer the occurrence's requested name."""
    with pytest.raises(ValueError, match="must match"):
        dependency_edge(binding(), target=binding("different"))


def test_edge_rejects_an_invalid_dependency_kind() -> None:
    """Dependency classifications remain the existing public enum."""
    with pytest.raises(ValueError, match="DependencyKind"):
        dependency_edge(binding(), kind=object())  # type: ignore[arg-type]


@pytest.mark.parametrize("path", [(), (FrameId(""),)])
def test_edge_rejects_an_invalid_lookup_path(path: tuple[FrameId, ...]) -> None:
    """Every occurrence records at least one valid searched Frame ID."""
    with pytest.raises(ValueError, match="lookup path cannot be empty"):
        dependency_edge(binding(), lookup_path=path)


def test_graph_rejects_an_empty_root() -> None:
    """A hierarchy snapshot always identifies its analyzed Frame."""
    with pytest.raises(ValueError, match="root cannot be empty"):
        FrameDependencyGraph(FrameId(""), (), (), ())


def test_graph_rejects_duplicate_bindings() -> None:
    """Definition and value vertex inventories are independently unique."""
    definition = binding()
    value = binding("host", kind=FrameBindingKind.VALUE)
    with pytest.raises(ValueError, match="definitions must be unique"):
        FrameDependencyGraph(FrameId("child"), (definition, definition), (), ())
    with pytest.raises(ValueError, match="values must be unique"):
        FrameDependencyGraph(FrameId("child"), (), (value, value), ())


def test_graph_rejects_foreign_edge_endpoints() -> None:
    """All resolved endpoints must belong to the immutable snapshot."""
    definition = binding()
    foreign_source = binding("foreign")
    foreign_value = binding("target", kind=FrameBindingKind.VALUE)
    with pytest.raises(ValueError, match="source must be a definition"):
        FrameDependencyGraph(
            FrameId("child"),
            (definition,),
            (),
            (dependency_edge(foreign_source),),
        )
    with pytest.raises(ValueError, match="target must belong"):
        FrameDependencyGraph(
            FrameId("child"),
            (definition,),
            (),
            (dependency_edge(definition, target=foreign_value),),
        )


def test_dependencies_rejects_a_foreign_source() -> None:
    """Outgoing queries distinguish absent definitions from empty edges."""
    definition = binding()
    graph = FrameDependencyGraph(FrameId("child"), (definition,), (), ())
    with pytest.raises(LclNameError, match="unknown Frame graph definition"):
        graph.dependencies(binding("foreign"))
