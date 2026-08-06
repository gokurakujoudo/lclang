"""Tests for the checked-in quality policy."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityConfigurationTests(unittest.TestCase):
    """Protect strict quality gates from accidental relaxation."""

    def setUp(self) -> None:
        """Load project configuration once for each isolated test."""
        with (ROOT / "pyproject.toml").open("rb") as stream:
            self.config = tomllib.load(stream)

    def test_development_group_contains_required_python_tools(self) -> None:
        """All verification tools must remain development-only dependencies."""
        names = {
            re.split(r"[<>=!~;\[]", item, maxsplit=1)[0]
            for item in self.config["dependency-groups"]["dev"]
        }
        self.assertTrue({"pytest", "pytest-cov", "mypy", "ruff", "build"} <= names)

    def test_coverage_requires_branches_and_ninety_nine_percent(self) -> None:
        """Coverage configuration must enforce the documented branch gate."""
        coverage = self.config["tool"]["coverage"]
        self.assertTrue(coverage["run"]["branch"])
        self.assertEqual(coverage["report"]["fail_under"], 99)

    def test_mypy_and_ruff_are_strict(self) -> None:
        """Type and lint configurations must retain their strict modes."""
        self.assertTrue(self.config["tool"]["mypy"]["strict"])
        self.assertEqual(self.config["tool"]["ruff"]["line-length"], 100)


if __name__ == "__main__":
    unittest.main()
