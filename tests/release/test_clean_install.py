"""Public smoke-program contract tests."""

from __future__ import annotations

from scripts.smoke_install import smoke_program


def test_smoke_program_is_standalone_and_records_both_artifact_paths() -> None:
    """The fixed program uses public APIs and emits machine-checkable evidence."""
    for kind in ("source-wheel", "sdist-wheel"):
        program = smoke_program(kind)
        assert "import pylcl" in program
        assert "from tests" not in program
        assert f"artifact={kind}" in program
        assert "closed=" in program
