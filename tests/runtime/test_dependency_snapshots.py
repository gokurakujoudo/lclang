"""Tests mirroring :mod:`pylcl.runtime.dependency_snapshots`."""

from dataclasses import FrozenInstanceError, replace

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import (
    DependencyEdge,
    DependencyKind,
    DependencySnapshot,
    reconcile_dependency_edges,
)
from pylcl.types import VarName


def _evidence() -> tuple[DependencyEdge, DependencyEdge]:
    span = parse_expression("target").span
    static = DependencyEdge(
        VarName("source"), VarName("target"), DependencyKind.EAGER, span
    )
    dynamic = replace(static, kind=DependencyKind.DYNAMIC)
    return static, dynamic


def test_dependency_snapshot_is_validated_immutable_evidence() -> None:
    """A snapshot binds matching static, dynamic, and reconciliation values."""
    static, dynamic = _evidence()
    reconciliation = reconcile_dependency_edges((static,), (dynamic,))
    snapshot = DependencySnapshot(
        VarName("source"),
        (static,),
        (dynamic,),
        reconciliation,
    )
    assert snapshot.reconciliation.confirmed == (static,)
    with pytest.raises(FrozenInstanceError):
        snapshot.source = VarName("other")  # type: ignore[misc]


def test_dependency_snapshot_rejects_inconsistent_manual_values() -> None:
    """Sources, channels, and reconciliation cannot contradict edge evidence."""
    static, dynamic = _evidence()
    reconciliation = reconcile_dependency_edges((static,), (dynamic,))
    with pytest.raises(ValueError, match="source"):
        DependencySnapshot(VarName(""), (), (), reconcile_dependency_edges((), ()))
    with pytest.raises(ValueError, match="source"):
        DependencySnapshot(VarName("other"), (static,), (), reconciliation)
    with pytest.raises(ValueError, match="reconciliation"):
        DependencySnapshot(
            VarName("source"),
            (static,),
            (dynamic,),
            reconcile_dependency_edges((static,), ()),
        )
