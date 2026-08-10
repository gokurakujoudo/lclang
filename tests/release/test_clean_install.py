"""Public smoke-program contract tests."""

from __future__ import annotations

from scripts.smoke_install import smoke_program


def test_smoke_program_is_standalone_and_records_both_artifact_paths() -> None:
    """The fixed program uses public APIs and emits machine-checkable evidence."""
    for kind in ("source-wheel", "sdist-wheel"):
        program = smoke_program(kind)
        compile(program, f"<{kind}-smoke>", "exec")
        assert "import lclang" in program
        assert "from lclang.config import load_config" in program
        assert "from lclang.cli import" in program
        assert 'using "共享.lclcfg"' in program
        assert 'len(config.history["base"]) == 2' in program
        assert 'await config_frame.get("answer") == 42' in program
        assert "from tests" not in program
        assert f"artifact={kind}" in program
        assert "closed=" in program
        assert "cli=" in program
        assert "dryrun=" in program
        assert "builtins=true logging=true exception=true" in program
        assert "redirect_stdout" in program
        assert "redirect_stderr" in program
