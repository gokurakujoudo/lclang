"""Structural acceptance for the audited Python module layout."""

from pathlib import Path

# Repository root containing production, maintenance, and mirrored test modules.
ROOT = Path(__file__).resolve().parents[1]
# Audited Python roots whose filenames must be recorded one by one.
IMPLEMENTATION_ROOTS = (ROOT / "pylcl", ROOT / "scripts", ROOT / "tests")
# New responsibility-based module locations selected by the audit.
EXPECTED_PATHS = (
    "pylcl/config/result.py",
    "pylcl/lang/evaluator/definition_context.py",
    "pylcl/lang/evaluator/dispatch.py",
    "pylcl/lang/evaluator/function_arguments.py",
    "pylcl/lang/evaluator/sync.py",
    "pylcl/lang/printer/dispatch.py",
    "pylcl/runtime/dependency/__init__.py",
    "pylcl/runtime/dependency/analysis.py",
    "pylcl/runtime/dependency/frame/__init__.py",
    "pylcl/runtime/dependency/frame/builder.py",
    "pylcl/runtime/dependency/frame/model.py",
    "pylcl/runtime/dependency/frame/resolution.py",
    "pylcl/runtime/dependency/graph.py",
    "pylcl/runtime/dependency/model.py",
    "pylcl/runtime/dependency/ordering.py",
    "pylcl/runtime/dependency/reconciliation.py",
    "pylcl/runtime/dependency/snapshot.py",
    "pylcl/runtime/dependency/tracing.py",
    "pylcl/runtime/frame/__init__.py",
    "pylcl/runtime/frame/closing.py",
    "pylcl/runtime/frame/core.py",
    "pylcl/runtime/frame/dependencies.py",
    "pylcl/runtime/frame/derivation.py",
    "pylcl/runtime/frame/evaluation.py",
    "pylcl/runtime/frame/factory.py",
    "pylcl/runtime/frame/flights.py",
    "pylcl/runtime/frame/inspection.py",
    "pylcl/runtime/frame/inspector.py",
    "pylcl/runtime/frame/lifecycle.py",
    "pylcl/runtime/frame/limits.py",
    "pylcl/runtime/frame/lookup.py",
    "pylcl/runtime/frame/recalculation.py",
    "pylcl/runtime/frame/values.py",
    "tests/lang/evaluator/test_definition_context.py",
    "tests/lang/evaluator/test_dispatch.py",
    "tests/lang/evaluator/test_function_arguments.py",
    "tests/lang/evaluator/test_sync.py",
    "tests/lang/printer/test_dispatch.py",
    "tests/runtime/dependency/frame/test_builder.py",
    "tests/runtime/dependency/frame/test_model.py",
    "tests/runtime/frame/test_core.py",
    "tests/runtime/frame/test_inspection.py",
)
# Superseded internal paths that would make ownership ambiguous if restored.
RETIRED_PATHS = (
    "pylcl/config/merge.py",
    "pylcl/lang/evaluator/evaluator.py",
    "pylcl/lang/printer/printer.py",
    "pylcl/runtime/definition_context.py",
    "pylcl/runtime/frame_dependency_graph.py",
    "pylcl/runtime/frame_dependency_resolution.py",
    "pylcl/runtime/frame_dependency_values.py",
    "pylcl/runtime/dependencies.py",
    "pylcl/runtime/dependency_analysis.py",
    "pylcl/runtime/dependency_graph.py",
    "pylcl/runtime/dependency_order.py",
    "pylcl/runtime/dependency_reconciliation.py",
    "pylcl/runtime/dependency_snapshots.py",
    "pylcl/runtime/dependency_tracing.py",
    "pylcl/runtime/frame_graph",
    "pylcl/runtime/flight.py",
    "pylcl/runtime/frame_dependencies.py",
    "pylcl/runtime/frame_derivation.py",
    "pylcl/runtime/frame_factory.py",
    "pylcl/runtime/frame_lookup.py",
    "pylcl/runtime/frame_values.py",
    "pylcl/runtime/frames.py",
    "pylcl/runtime/lifecycle.py",
    "pylcl/runtime/limits.py",
    "pylcl/runtime/recalculation.py",
)


def test_every_implementation_filename_is_audited_and_concise() -> None:
    """Every Python basename has a recorded decision and at most five words."""
    audit = (ROOT / "docs" / "architecture" / "python-file-name-audit.md").read_text(
        encoding="utf-8"
    )
    paths = tuple(
        path
        for directory in IMPLEMENTATION_ROOTS
        for path in sorted(directory.rglob("*.py"))
    )
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        assert f"`{relative}`" in audit
        if path.stem != "__init__":
            assert len(path.stem.split("_")) <= 5


def test_audited_moves_are_complete_and_tests_mirror_nested_packages() -> None:
    """Selected paths exist atomically while every retired ambiguous path stays absent."""
    assert all((ROOT / path).is_file() for path in EXPECTED_PATHS)
    assert all(not (ROOT / path).exists() for path in RETIRED_PATHS)
