"""Unit tests mirroring :mod:`lclang.config.files`."""

from pathlib import Path

import pytest

from lclang.config import FileConfigResolver, LclConfigUsingError, load_config


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
