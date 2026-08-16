"""Acceptance tests mirroring the stable package-root runtime API."""

import pytest

import lclang
from lclang.runtime import (
    NO_FALLBACK,
    DependencySnapshot,
    EvaluationLimits,
    Frame,
    FrameFactory,
    Module,
    Preset,
)
from lclang.stdlib import STANDARD_PRESET


def test_root_runtime_exports_are_canonical_and_listed_once() -> None:
    """Primary runtime values retain one canonical implementation identity."""
    expected = {
        "LCL_BUILTINS": lclang.LCL_BUILTINS,
        "LCL_IMPORTS": lclang.LCL_IMPORTS,
        "LCL_ROOT": lclang.LCL_ROOT,
        "LCL_RUNTIME": lclang.LCL_RUNTIME,
        "DependencySnapshot": DependencySnapshot,
        "EvaluationLimits": EvaluationLimits,
        "Frame": Frame,
        "FrameFactory": FrameFactory,
        "Module": Module,
        "NO_FALLBACK": NO_FALLBACK,
        "Preset": Preset,
        "STANDARD_PRESET": STANDARD_PRESET,
    }
    for name, value in expected.items():
        assert getattr(lclang, name) is value
        assert lclang.__all__.count(name) == 1


def test_advanced_runtime_and_stdlib_construction_remain_namespaced() -> None:
    """The root API stays focused on daily construction and evaluation."""
    assert not hasattr(lclang, "build_dependency_graph")
    assert not hasattr(lclang, "reconcile_dependency_edges")
    assert not hasattr(lclang, "StdlibManifest")
    assert not hasattr(lclang, "STANDARD_MANIFESTS")
    assert not hasattr(lclang, "collect")


@pytest.mark.asyncio
async def test_root_only_runtime_workflow_evaluates_inspects_and_closes() -> None:
    """One root import supports the complete public runtime workflow."""
    module = lclang.define_module(
        "app",
        {"value": 'json.encode({"answer": 42})'},
    )
    async with lclang.define_frame(module) as frame:
        assert await frame.get("value") == '{"answer":42}'
        snapshot = frame.dependency_snapshot("value")
        assert isinstance(snapshot, lclang.DependencySnapshot)
        assert tuple(edge.target for edge in snapshot.dynamic_edges) == ("json",)
    assert frame.closed is True


def test_root_direct_frame_construction_remains_available() -> None:
    """Factory integration does not remove the explicit Frame constructor."""
    module = lclang.Module(
        lclang.ModuleName("app"),
        {"value": lclang.parse_expression("host")},
    )
    frame = lclang.Frame(module, lclang.FrameId("direct"), values={"host": 1})
    assert frame.module is module
