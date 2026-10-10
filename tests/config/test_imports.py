"""Independent named imports and chronological configuration composition."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.config import load_config
from lclang.lang import FrameProxy


@pytest.mark.asyncio
async def test_import_qualifies_local_references_and_preserves_external_inputs() -> None:
    """Imported locals are qualified while undeclared inputs remain external."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text(
            'x: 100\nimport "part.lclcfg" as m\nm.x: 7\nresult: m.y\n', encoding="utf-8"
        )
        (root / "part.lclcfg").write_text("x: 2\ny: x + seed\n", encoding="utf-8")
        config = await load_config(root / "main.lclcfg")
        assert list(config.definitions) == ["x", "m.x", "m.y", "result"]
        assert len(config.history["m.x"]) == 2
        assert config.history["m.x"][0].span.origin.path == root / "part.lclcfg"
        async with config.to_frame(preset={"seed": 3}) as frame:
            assert await frame.get("result") == 10


@pytest.mark.asyncio
async def test_import_keeps_lexical_parameter_names() -> None:
    """An alias cannot capture a parameter with the same spelling."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text('import "part.lclcfg" as m\n', encoding="utf-8")
        (root / "part.lclcfg").write_text("x: 2\nf: m -> x + m\ny: f(3)\n", encoding="utf-8")
        config = await load_config(root / "main.lclcfg")
        async with config.to_frame() as frame:
            assert await frame.get("m.y") == 5


@pytest.mark.asyncio
async def test_optional_import_omits_missing_namespace_but_keeps_empty_file() -> None:
    """Existing empty imports reserve a namespace; absent imports contribute nothing."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text(
            'import? "absent.lclcfg" as absent\nimport "empty.lclcfg" as empty\n',
            encoding="utf-8",
        )
        (root / "empty.lclcfg").write_text("", encoding="utf-8")
        config = await load_config(root / "main.lclcfg")
        assert config.namespace_names == frozenset({"empty"})
        assert dict(config.history) == {}
        async with config.to_frame() as frame:
            proxy = await frame.get("empty")
            assert isinstance(proxy, FrameProxy)
            assert await proxy.field_names() == []
