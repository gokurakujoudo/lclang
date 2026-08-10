"""Stable release metadata contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

import lclang
from scripts.inspect_package import VERSION

# Repository root containing package metadata.
ROOT = Path(__file__).resolve().parents[2]
# Stable public release version.
RELEASE = "1.0.0"


def test_release_metadata_is_coherent() -> None:
    """Distribution, runtime, and artifact tooling report the stable release."""
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["version"] == RELEASE
    assert lclang.__version__ == RELEASE
    assert VERSION == RELEASE
    assert project["requires-python"] == ">=3.14"
    assert "dependencies" not in project
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
