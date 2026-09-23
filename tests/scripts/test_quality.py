"""Contracts for the fail-fast maintenance loop."""

from pathlib import Path
from unittest.mock import patch

from scripts.quality import quality_commands, run_commands


def test_quality_orders_fast_checks_before_documentation_and_behavior() -> None:
    """Expensive behavioral coverage runs last and includes every non-doc test."""
    assert quality_commands(Path("python")) == (
        ("git", "diff", "--check"),
        ("python", "-m", "ruff", "check", "."),
        ("python", "-m", "scripts.check_project"),
        ("python", "-m", "scripts.security_audit"),
        ("python", "-m", "mypy"),
        ("python", "-m", "pyright"),
        (
            "python", "-m", "pytest", "-m", "docs", "--no-cov",
            "--junitxml=reports/tests-docs.xml",
        ),
        (
            "python", "-m", "pytest", "-m", "not docs",
            "--junitxml=reports/tests-behavior.xml",
            "--cov-report=xml:reports/coverage.xml",
            "--cov-report=json:reports/coverage.json",
            "--cov-report=html:reports/htmlcov",
        ),
    )


def test_quality_stops_after_first_failed_command() -> None:
    """A failed early check never launches later tools."""
    with patch("scripts.quality.subprocess.run") as run:
        run.return_value.returncode = 3
        assert run_commands((("first",), ("second",))) == 3
        assert run.call_count == 1
        run.return_value.returncode = 0
        assert run_commands((("first",), ("second",))) == 0
