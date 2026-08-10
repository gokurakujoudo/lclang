"""Unit tests mirroring :mod:`lclang.stdlib.manifest`."""

from dataclasses import FrozenInstanceError

import pytest

from lclang.stdlib import StdlibEntry, StdlibManifest


def test_entry_retains_opaque_value_and_immutable_metadata() -> None:
    """Manifest metadata never copies or invokes an exported value."""
    value = {"opaque": True}
    entry = StdlibEntry("constant", value, "One opaque constant.")
    assert entry.value is value
    with pytest.raises(FrozenInstanceError):
        entry.name = "other"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["", "not-valid", "class", "_private", "items"])
def test_entry_rejects_invalid_or_reserved_export_names(name: str) -> None:
    """Exports must be reachable unambiguously through LCL attribute syntax."""
    with pytest.raises(ValueError):
        StdlibEntry(name, object(), "Valid summary.")


@pytest.mark.parametrize("summary", ["", "   ", "two\nlines"])
def test_entry_requires_a_non_blank_one_line_summary(summary: str) -> None:
    """Every reviewed export carries concise stable manifest documentation."""
    with pytest.raises(ValueError):
        StdlibEntry("value", object(), summary)


def test_manifest_detaches_ordered_entries_and_rejects_duplicates() -> None:
    """Declaration order is immutable and names are unique per namespace."""
    first = StdlibEntry("first", 1, "First value.")
    second = StdlibEntry("second", 2, "Second value.")
    entries = [first, second]
    manifest = StdlibManifest("tools", entries)
    entries.clear()
    assert manifest.entries == (first, second)
    with pytest.raises(ValueError, match="duplicate"):
        StdlibManifest("tools", (first, first))
    with pytest.raises(TypeError):
        StdlibManifest("tools", (object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        StdlibManifest("not-valid", ())
