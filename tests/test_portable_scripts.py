"""Tests for platform-neutral project automation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from scripts.quality import quality_commands
from scripts.smoke_install import venv_python


class PortableScriptTests(unittest.TestCase):
    """Lock portable command construction without spawning subprocesses."""

    def test_quality_commands_are_fail_fast_and_use_current_python(self) -> None:
        """The quality gate must execute every authoritative checker in order."""
        commands = quality_commands(Path(sys.executable))
        modules = [
            command[2] if command[:2] == (sys.executable, "-m") else command[0]
            for command in commands
        ]
        self.assertEqual(modules, ["pytest", "mypy", "ruff", "scripts.check_project", "git"])

    def test_virtual_environment_python_path_is_platform_specific(self) -> None:
        """Smoke installation must locate Python on Windows and POSIX."""
        root = Path("environment")
        self.assertEqual(venv_python(root, "nt"), root / "Scripts" / "python.exe")
        self.assertEqual(venv_python(root, "posix"), root / "bin" / "python")
