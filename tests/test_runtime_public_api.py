"""Acceptance tests mirroring the stable package-root runtime API."""

import pytest

import pylcl
from pylcl.runtime import (
    DependencySnapshot,
    EvaluationLimits,
    Frame,
    FrameFactory,
    Module,
    Preset,
)
from pylcl.stdlib import STANDARD_PRESET


def test_root_runtime_exports_are_canonical_and_listed_once() -> None:
    """Primary runtime values retain one canonical implementation identity."""
    expected = {
        "LCL_BUILTINS": pylcl.LCL_BUILTINS,
        "LCL_IMPORTS": pylcl.LCL_IMPORTS,
        "LCL_ROOT": pylcl.LCL_ROOT,
        "LCL_RUNTIME": pylcl.LCL_RUNTIME,
        "DependencySnapshot": DependencySnapshot,
        "EvaluationLimits": EvaluationLimits,
        "Frame": Frame,
        "FrameFactory": FrameFactory,
        "Module": Module,
        "Preset": Preset,
        "STANDARD_PRESET": STANDARD_PRESET,
    }
    for name, value in expected.items():
        assert getattr(pylcl, name) is value
        assert pylcl.__all__.count(name) == 1


def test_advanced_runtime_and_stdlib_construction_remain_namespaced() -> None:
    """The root API stays focused on daily construction and evaluation."""
    assert not hasattr(pylcl, "build_dependency_graph")
    assert not hasattr(pylcl, "reconcile_dependency_edges")
    assert not hasattr(pylcl, "StdlibManifest")
    assert not hasattr(pylcl, "STANDARD_MANIFESTS")
    assert not hasattr(pylcl, "collect")


@pytest.mark.asyncio
async def test_root_only_runtime_workflow_evaluates_inspects_and_closes() -> None:
    """One root import supports the complete intended 0.1 user workflow."""
    module = pylcl.define_module(
        "app",
        {"value": 'json.encode({"answer": 42})'},
    )
    frame = pylcl.define_frame(module)
    assert await frame.get("value") == '{"answer":42}'
    snapshot = frame.dependency_snapshot("value")
    assert isinstance(snapshot, pylcl.DependencySnapshot)
    assert tuple(edge.target for edge in snapshot.dynamic_edges) == ("json",)
    await frame.close()
    assert frame.closed is True


def test_root_direct_frame_construction_remains_available() -> None:
    """Factory integration does not remove the explicit Frame constructor."""
    module = pylcl.Module(
        pylcl.ModuleName("app"),
        {"value": pylcl.parse_expression("host")},
    )
    frame = pylcl.Frame(module, pylcl.FrameId("direct"), values={"host": 1})
    assert frame.module is module
