"""Read authoritative release metadata for maintenance commands."""

from __future__ import annotations

import tomllib
from pathlib import Path

# Repository root containing authoritative project metadata.
ROOT = Path(__file__).resolve().parents[1]


def project_version(root: Path = ROOT) -> str:
    """Return the non-empty distribution version from project metadata.

    :param root: Project root containing ``pyproject.toml``.
    :returns: Exact PEP 621 project version text.
    :raises OSError: If metadata cannot be read.
    :raises KeyError: If required metadata fields are absent.
    :raises ValueError: If the version is not non-empty text.
    """
    with (root / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if not isinstance(version, str) or not version:
        raise ValueError("project version must be non-empty text")
    return version
