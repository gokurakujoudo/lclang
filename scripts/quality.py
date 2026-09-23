"""Run the authoritative lclang quality gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Command = tuple[str, ...]


def quality_commands(python: Path) -> tuple[Command, ...]:
    """Return quality commands in their fail-fast order.

    :param python: Python interpreter used for module-based tools.
    :returns: Immutable command sequence.
    """
    executable = str(python)
    return (
        ("git", "diff", "--check"),
        (executable, "-m", "ruff", "check", "."),
        (executable, "-m", "scripts.check_project"),
        (executable, "-m", "scripts.security_audit"),
        (executable, "-m", "mypy"),
        (executable, "-m", "pyright"),
        (
            executable, "-m", "pytest", "-m", "docs", "--no-cov",
            "--junitxml=reports/tests-docs.xml",
        ),
        (
            executable, "-m", "pytest", "-m", "not docs",
            "--junitxml=reports/tests-behavior.xml",
            "--cov-report=xml:reports/coverage.xml",
            "--cov-report=json:reports/coverage.json",
            "--cov-report=html:reports/htmlcov",
        ),
    )


def run_commands(commands: tuple[Command, ...], cwd: Path = ROOT) -> int:
    """Run commands until one fails.

    :param commands: Commands to execute.
    :param cwd: Working directory shared by every command.
    :returns: Zero on success or the first failing return code.
    """
    for command in commands:
        result = subprocess.run(command, cwd=cwd, check=False)
        if result.returncode:
            return result.returncode
    return 0


def main() -> int:
    """Run the complete quality gate with the active interpreter.

    :returns: Zero only when every checker succeeds.
    """
    return run_commands(quality_commands(Path(sys.executable)))


if __name__ == "__main__":
    sys.exit(main())
