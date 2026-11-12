"""LCL integration for the text file builtin."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.error import LclStandardError
from lclang.lang import define_frame, define_module


@pytest.mark.asyncio
async def test_text_file_builtin_composition_and_snapshots() -> None:
    """Named reads cache snapshots; recalculation does not invalidate dependants."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "text.txt"
        path.write_bytes("中文\nsecond".encode("gbk"))
        module = define_module(
            "files",
            {
                "content": 'read_text_file(fp, encoding="gbk")',
                "positional": 'read_text_file(fp, "gbk")',
                "lines": "text.lines(content)",
            },
        )
        async with define_frame(module, preset={"fp": path}) as frame:
            assert await frame.get("content") == "中文\nsecond"
            assert await frame.get("positional") == "中文\nsecond"
            assert await frame.get("lines") == ["中文", "second"]
            path.write_text("changed", encoding="utf-8")
            assert await frame.get("content") == "中文\nsecond"
            assert await frame.recalculate("content") == "changed"
            assert await frame.get("lines") == ["中文", "second"]
            assert await frame.recalculate("lines") == ["changed"]


@pytest.mark.asyncio
async def test_text_file_builtin_failure_keeps_source_and_cause() -> None:
    """The normal call boundary retains file diagnostics and the source span."""
    with TemporaryDirectory() as directory:
        module = define_module("files", {"content": "read_text_file(fp)"})
        async with define_frame(module, preset={"fp": str(Path(directory) / "missing")}) as frame:
            with pytest.raises(LclStandardError) as caught:
                await frame.get("content")
            assert caught.value.code == "LCL981711"
            assert isinstance(caught.value.__cause__, FileNotFoundError)
            assert caught.value.span is not None
