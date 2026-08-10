"""Behavioural tests for the distribution skeleton."""

from __future__ import annotations

import importlib
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    """Verify the public distribution and import metadata contract."""

    def test_project_metadata_targets_python_314_without_runtime_deps(self) -> None:
        """The package must be Python 3.14-only and dependency-free at runtime."""
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]

        self.assertEqual(project["name"], "pylcl")
        self.assertEqual(project["requires-python"], ">=3.14")
        self.assertNotIn("dependencies", project)

    def test_import_exposes_release_version(self) -> None:
        """Importing the package must expose the coherent 0.3 release version."""
        module = importlib.import_module("pylcl")
        self.assertEqual(module.__version__, "0.3.0")
        self.assertTrue((ROOT / "pylcl" / "py.typed").is_file())


if __name__ == "__main__":
    unittest.main()
