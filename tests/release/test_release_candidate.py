"""Release orchestration failure-safety tests."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from scripts.build_package import ensure_empty_output
from scripts.inspect_package import ArtifactReport
from scripts.release_candidate import artifact_record, safe_extract


def test_existing_output_and_archive_traversal_are_rejected(tmp_path: Path) -> None:
    """Rainy release inputs never overwrite output or escape extraction."""
    output = tmp_path / "output"
    output.mkdir()
    (output / "caller.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        ensure_empty_output(output)
    archive_path = tmp_path / "bad.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("../outside.txt")
        member.size = 0
        archive.addfile(member)
    with pytest.raises(ValueError, match="escapes"):
        safe_extract(archive_path, tmp_path / "extract")
    assert (output / "caller.txt").read_text(encoding="utf-8") == "keep"


def test_artifact_record_is_stable_for_composite_evidence(tmp_path: Path) -> None:
    """Sunny artifact evidence retains names, sizes, member counts, and digests."""
    path = tmp_path / "pylcl-0.1.0.whl"
    path.write_bytes(b"wheel")
    report = ArtifactReport(path, "wheel", ("pylcl/py.typed",), {"Version": "0.1.0"}, "abc")
    record = artifact_record((report,))
    assert '"version": "0.1.0"' in record
    assert '"sha256": "abc"' in record
