"""Unit tests mirroring :mod:`lclang.config.sources`."""

from pathlib import Path

import pytest

from lclang.config import LclConfigUsingError, ResolvedConfigSource
from lclang.config.sources import canonical_config_path, resolve_using_path


def test_resolved_source_and_root_path_validation(tmp_path: Path) -> None:
    """Resolver results require stable identity, display text, Unicode, and suffix."""
    path = tmp_path / "source.lclcfg"
    with pytest.raises(ValueError):
        ResolvedConfigSource("", "source", path, "")
    with pytest.raises(ValueError):
        ResolvedConfigSource("id", "", path, "")
    with pytest.raises(ValueError):
        ResolvedConfigSource("id", "source", "bad", "")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ResolvedConfigSource("id", "source", tmp_path / "bad.txt", "")
    with pytest.raises(ValueError):
        ResolvedConfigSource("id", "source", path, b"bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        canonical_config_path(1)  # type: ignore[arg-type]
    with pytest.raises(LclConfigUsingError):
        canonical_config_path(tmp_path / "bad.txt")


def test_using_path_modes_are_canonical_and_suffix_checked(tmp_path: Path) -> None:
    """Relative, absolute, leading-magic, and invalid targets take distinct paths."""
    importer_path = (tmp_path / "nested" / "root.lclcfg").resolve()
    importer = ResolvedConfigSource("root", "root", importer_path, "")
    assert resolve_using_path("child.lclcfg", importer) == importer_path.parent / "child.lclcfg"
    absolute = (tmp_path / "absolute.lclcfg").resolve()
    assert resolve_using_path(str(absolute), importer) == absolute
    assert (
        resolve_using_path("__dir__/../shared.lclcfg", importer)
        == (tmp_path / "shared.lclcfg").resolve()
    )
    with pytest.raises(LclConfigUsingError):
        resolve_using_path("__dir__", importer)
    with pytest.raises(LclConfigUsingError):
        resolve_using_path("bad.txt", importer)
