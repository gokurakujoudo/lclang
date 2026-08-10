"""Tests for the checked-in quality policy."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".gitlab-ci.yml"

# Exact direct toolchain installed in the verified local environment.
DEVELOPMENT_REQUIREMENTS = [
    "build==1.5.0",
    "hatchling==1.31.0",
    "hypothesis==6.165.0",
    "mypy==2.3.0",
    "pytest==9.1.1",
    "pytest-asyncio==1.4.0",
    "pytest-cov==7.1.0",
    "ruff==0.16.1",
]


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

    def test_coverage_requires_branches_and_full_coverage(self) -> None:
        """Coverage configuration must enforce the documented branch gate."""
        coverage = self.config["tool"]["coverage"]
        self.assertTrue(coverage["run"]["branch"])
        self.assertEqual(coverage["report"]["fail_under"], 100)
        pytest_options = self.config["tool"]["pytest"]["ini_options"]["addopts"]
        self.assertIn("--cov-fail-under=100", pytest_options)

    def test_mypy_and_ruff_are_strict(self) -> None:
        """Type and lint configurations must retain their strict modes."""
        self.assertTrue(self.config["tool"]["mypy"]["strict"])
        self.assertEqual(self.config["tool"]["ruff"]["line-length"], 100)

    def test_ci_uses_the_exact_local_toolchain(self) -> None:
        """CI must consume the exact checked-in local development tool groups."""
        groups = self.config["dependency-groups"]
        self.assertEqual(groups["dev"], DEVELOPMENT_REQUIREMENTS)
        self.assertEqual(groups["publish"], ["twine==6.2.0"])
        self.assertEqual(self.config["build-system"]["requires"], ["hatchling==1.31.0"])
        pipeline = CI_PATH.read_text(encoding="utf-8")
        self.assertIn('PYLCL_CI_PIP_VERSION: "25.3"', pipeline)
        self.assertEqual(pipeline.count("--group dev"), 1)
        self.assertEqual(pipeline.count("--group publish"), 2)
        for requirement in [*DEVELOPMENT_REQUIREMENTS, "twine==6.2.0"]:
            self.assertNotIn(f'"{requirement}"', pipeline)

    def test_ci_verification_reuses_one_job_environment(self) -> None:
        """Setup, build, test, and inspection must run in one CI container."""
        pipeline = CI_PATH.read_text(encoding="utf-8")
        self.assertRegex(pipeline, r"(?ms)^stages:\s+- verify\s+- publish\s*$")
        self.assertIn("verify:\n  stage: verify", pipeline)
        for legacy_job in ("setup", "build", "test"):
            self.assertNotIn(f"\n{legacy_job}:\n", pipeline)
        verify = pipeline.split("verify:\n", 1)[1].split("publish-artifactory:", 1)[0]
        commands = (
            "--group dev",
            "python -m pip check",
            "python -m scripts.build_package --output dist",
            "python -m scripts.quality",
            "python -m coverage xml -o coverage.xml",
            "package inspection: PASS",
        )
        positions = [verify.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(pipeline.count("artifacts: true"), 2)


if __name__ == "__main__":
    unittest.main()
