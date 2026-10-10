"""Unit tests mirroring :mod:`lclang.lang.runtime.dependency.dependency_types`."""

import pytest

from lclang.common.identifiers import VarName
from lclang.error import LclAttributeError, LclValidationError
from lclang.lang.engine.parser import parse_expression
from lclang.lang.runtime import DependencyEdge, DependencyKind, DependencyReference


def test_dependency_kinds_have_stable_public_values() -> None:
    """Edge classifications serialize to durable lowercase labels."""
    assert tuple(kind.value for kind in DependencyKind) == (
        "eager",
        "conditional",
        "deferred",
        "dynamic",
    )


def test_dependency_reference_retains_name_kind_and_span() -> None:
    """One syntactic occurrence remains immutable diagnostic evidence."""
    span = parse_expression("value").span
    reference = DependencyReference(VarName("value"), DependencyKind.EAGER, span)
    assert reference.name == VarName("value")
    assert reference.kind is DependencyKind.EAGER
    assert reference.span is span
    with pytest.raises(LclAttributeError):
        reference.name = VarName("other")  # type: ignore[misc]


def test_dependency_reference_rejects_invalid_public_values() -> None:
    """Empty names and non-enum kinds cannot enter dependency graphs."""
    span = parse_expression("value").span
    with pytest.raises(LclValidationError):
        DependencyReference(VarName(""), DependencyKind.EAGER, span)
    with pytest.raises(LclValidationError):
        DependencyReference(VarName("value"), "eager", span)  # type: ignore[arg-type]


def test_dependency_edge_validates_both_endpoints_and_kind() -> None:
    """Graph edges retain occurrence spans and reject invalid vocabulary."""
    span = parse_expression("target").span
    edge = DependencyEdge(
        VarName("source"),
        VarName("target"),
        DependencyKind.CONDITIONAL,
        span,
    )
    assert edge.span is span
    with pytest.raises(LclValidationError):
        DependencyEdge(VarName(""), VarName("target"), DependencyKind.EAGER, span)
    with pytest.raises(LclValidationError):
        DependencyEdge(VarName("source"), VarName(""), DependencyKind.EAGER, span)
    with pytest.raises(LclValidationError):
        DependencyEdge(VarName("source"), VarName("target"), "eager", span)  # type: ignore[arg-type]
