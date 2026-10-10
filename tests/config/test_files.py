"""Unit tests mirroring :mod:`lclang.config.files`."""

import asyncio
import os
from pathlib import Path
from stat import S_IFIFO
from tempfile import TemporaryDirectory

import pytest

from lclang.config import FileConfigResolver, load_config
from lclang.config.files import read_file_source
from lclang.error import LclConfigUsingError


@pytest.mark.asyncio
async def test_filesystem_bom_containment_decode_and_file_kinds(tmp_path: Path) -> None:
    """Filesystem retrieval accepts a BOM and structures all practical failures."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    good = allowed / "good.lclcfg"
    good.write_bytes(b"\xef\xbb\xbfvalue: 1\n")
    assert "value" in (await load_config(good, resolver=FileConfigResolver(allowed))).definitions
    outside = tmp_path / "outside.lclcfg"
    outside.write_text("value: 1\n", encoding="utf-8")
    with pytest.raises(LclConfigUsingError):
        await load_config(outside, resolver=FileConfigResolver(allowed))
    directory = allowed / "folder.lclcfg"
    directory.mkdir()
    with pytest.raises(LclConfigUsingError):
        await load_config(directory)
    invalid = allowed / "invalid.lclcfg"
    invalid.write_bytes(b"\xff")
    with pytest.raises(LclConfigUsingError):
        await load_config(invalid)


def test_non_regular_source_is_not_reported_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A portable special-file status remains a read error, not optional absence."""
    with TemporaryDirectory(prefix="lclang-special-config-") as directory:
        path = (Path(directory) / "special.lclcfg").resolve()
        status = os.stat_result((S_IFIFO, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        def read_special_status(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
            """Return the injected FIFO mode without creating a platform-specific FIFO."""
            del self, follow_symlinks
            return status

        with monkeypatch.context() as patch:
            patch.setattr(Path, "stat", read_special_status)
            with pytest.raises(LclConfigUsingError, match="not a regular file") as caught:
                read_file_source(path, None)
        assert not isinstance(caught.value, FileNotFoundError)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["stat", "read"])
@pytest.mark.parametrize("failure_type", [PermissionError, OSError])
async def test_optional_source_keeps_filesystem_access_failures(
    stage: str, failure_type: type[OSError], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Errors from actual file status and byte-reading boundaries are never absence."""
    with TemporaryDirectory(prefix="lclang-config-access-") as directory:
        root = await asyncio.to_thread(Path(directory).resolve)
        entry = root / "root.lclcfg"
        child = root / "child.lclcfg"
        entry.write_text('value: 1\nusing? "child.lclcfg"\n', encoding="utf-8")
        child.write_text("value: 42\n", encoding="utf-8")
        failure = failure_type("injected access failure")
        original_stat = Path.stat
        original_read = Path.read_bytes

        def read_status(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
            """Inject a status error only for the requested optional child."""
            if self == child:
                raise failure
            return original_stat(self, follow_symlinks=follow_symlinks)

        def read_bytes(self: Path) -> bytes:
            """Inject a read error only after the optional child's status succeeds."""
            if self == child:
                raise failure
            return original_read(self)

        with monkeypatch.context() as patch:
            if stage == "stat":
                patch.setattr(Path, "stat", read_status)
            else:
                patch.setattr(Path, "read_bytes", read_bytes)
            with pytest.raises(LclConfigUsingError) as caught:
                await load_config(entry)
        assert caught.value.__cause__ is failure


@pytest.mark.asyncio
async def test_optional_source_disappearing_before_read_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file removed after status checking is still directly missing at retrieval."""
    with TemporaryDirectory(prefix="lclang-config-disappearance-") as directory:
        root = await asyncio.to_thread(Path(directory).resolve)
        entry = root / "root.lclcfg"
        child = root / "child.lclcfg"
        entry.write_text('value: 1\nusing? "child.lclcfg"\n', encoding="utf-8")
        child.write_text("value: 42\n", encoding="utf-8")
        original_read = Path.read_bytes

        def read_after_removal(self: Path) -> bytes:
            """Delete the child exactly at the read boundary and perform the real read."""
            if self == child:
                child.unlink()
            return original_read(self)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "read_bytes", read_after_removal)
            config = await load_config(entry)
        assert not child.exists()
        assert len(config.history["value"]) == 1
        async with config.to_frame() as frame:
            assert await frame.get("value") == 1
