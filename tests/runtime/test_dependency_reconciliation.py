"""Tests mirroring :mod:`pylcl.runtime.dependency_reconciliation`."""

from dataclasses import FrozenInstanceError

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import (
    DependencyEdge,
    DependencyKind,
    reconcile_dependency_edges,
)
from pylcl.types import VarName


def _edge(
    source: str,
    target: str,
    kind: DependencyKind,
    expression: str,
) -> DependencyEdge:
    return DependencyEdge(
        VarName(source),
        VarName(target),
        kind,
        parse_expression(expression).span,
    )


def test_reconciliation_partitions_edges_in_their_input_orders() -> None:
    """Observed static occurrences retain their classification and order."""
    eager = _edge("item", "first", DependencyKind.EAGER, "first")
    optional = _edge("item", "later", DependencyKind.CONDITIONAL, " later")
    observed = DependencyEdge(
        optional.source,
        optional.target,
        DependencyKind.DYNAMIC,
        optional.span,
    )
    unexpected = _edge("item", "runtime", DependencyKind.DYNAMIC, "runtime")
    result = reconcile_dependency_edges((eager, optional), (observed, unexpected))
    assert result.confirmed == (optional,)
    assert result.inactive == (eager,)
    assert result.unexpected == (unexpected,)
    with pytest.raises(FrozenInstanceError):
        result.confirmed = ()  # type: ignore[misc]


def test_matching_requires_the_exact_occurrence_span() -> None:
    """A same-name lookup at another span remains unexpected evidence."""
    static = _edge("item", "value", DependencyKind.EAGER, "value")
    dynamic = _edge("item", "value", DependencyKind.DYNAMIC, " value")
    result = reconcile_dependency_edges((static,), (dynamic,))
    assert result.confirmed == ()
    assert result.inactive == (static,)
    assert result.unexpected == (dynamic,)


def test_reconciliation_accepts_empty_inputs() -> None:
    """An unevaluated definition can have an empty comparison snapshot."""
    result = reconcile_dependency_edges((), ())
    assert result.confirmed == result.inactive == result.unexpected == ()


def test_reconciliation_rejects_edges_in_the_wrong_channels() -> None:
    """Static predictions and dynamic observations use disjoint vocabularies."""
    static = _edge("item", "value", DependencyKind.EAGER, "value")
    dynamic = _edge("item", "value", DependencyKind.DYNAMIC, "value")
    with pytest.raises(ValueError, match="static"):
        reconcile_dependency_edges((dynamic,), ())
    with pytest.raises(ValueError, match="dynamic"):
        reconcile_dependency_edges((), (static,))
