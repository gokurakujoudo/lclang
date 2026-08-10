"""Archive inspection tests for sunny, rainy, and composite release cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.inspect_package import (
    VERSION,
    inspect_sdist,
    inspect_wheel,
    metadata_fields,
    normalized_wheel_members,
)
from tests.release.support import sdist_fixture, wheel_fixture


def test_valid_wheel_and_sdist_have_coherent_release_reports(tmp_path: Path) -> None:
    """A complete pair passes metadata, member, and normalized-set inspection."""
    wheel = wheel_fixture(tmp_path / f"lclang-{VERSION}-py3-none-any.whl")
    sdist = sdist_fixture(tmp_path / f"lclang-{VERSION}.tar.gz")
    assert inspect_wheel(wheel).metadata["Version"] == VERSION
    assert inspect_sdist(sdist).metadata["Name"] == "lclang"
    assert "lclang/__init__.py" in normalized_wheel_members(wheel)


def test_wheel_rejects_injected_repository_member(tmp_path: Path) -> None:
    """A wheel containing an unrelated member fails without modifying the archive."""
    wheel = wheel_fixture(
        tmp_path / f"lclang-{VERSION}-py3-none-any.whl",
        ("tests/injected.py",),
    )
    with pytest.raises(ValueError, match="repository"):
        inspect_wheel(wheel)


def test_sdist_rejects_cache_member_and_metadata_rejects_dependency(tmp_path: Path) -> None:
    """Composite rainy input rejects both source caches and runtime dependencies."""
    sdist = sdist_fixture(tmp_path / f"lclang-{VERSION}.tar.gz", ("src/lclang/__pycache__/x.pyc",))
    with pytest.raises(ValueError, match="ignored"):
        inspect_sdist(sdist)
    raw = (
        f"Name: lclang\nVersion: {VERSION}\nRequires-Python: >=3.14\n"
        "License: MIT\nRequires-Dist: bad\n"
    )
    with pytest.raises(ValueError, match="dependency"):
        metadata_fields(raw)
