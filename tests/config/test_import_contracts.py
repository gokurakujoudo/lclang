"""Composite, invalid, and independently scoped file-import contracts."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import pytest

from lclang.config import (
    ConfigImport,
    ConfigLoader,
    FileConfigResolver,
    LclConfigCycleError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    load_config,
    parse_config,
)
from lclang.error import LclEvaluationError, LclValidationError
from tests.config.support import source_span


@pytest.mark.parametrize(
    "text",
    [
        'import "a.lclcfg"',
        'import "a.lclcfg" as',
        'import "a.lclcfg" as a as b',
        'import "a.lclcfg" as x-y',
        'import "a.lclcfg" as __private',
        'import "a.lclcfg" as True',
        'import "a.json" as a',
        "import 42 as a",
        'import "a.lclcfg" as a \\\n x: 1',
        'import?"a.lclcfg" as a',
    ],
)
def test_import_rejects_invalid_targets_and_aliases(text: str) -> None:
    """Imports require a file target, delimiter, and static non-reserved alias."""
    with pytest.raises(LclConfigSyntaxError):
        parse_config(text)


def test_import_public_model_and_expression_coordinates() -> None:
    """Optional syntax preserves indentation, comments, and the target's physical span."""
    document = parse_config('  import? f"parts/{profile}.lclcfg" as services.db # note\r\n')
    declaration = document.declarations[0]
    assert isinstance(declaration, ConfigImport)
    assert declaration.optional is True
    assert declaration.alias == "services.db"
    assert not isinstance(declaration.target, str)
    assert declaration.target.span.start.column == 11
    assert declaration.target.span.snapshot is not None
    with pytest.raises(LclValidationError, match="Boolean"):
        ConfigImport("a.lclcfg", source_span(), 0, "a", 1)  # type: ignore[arg-type]
    with pytest.raises(LclValidationError, match="reserved"):
        ConfigImport("a.lclcfg", source_span(), 0, "__private")
    for span, ordinal in ((1, 0), (source_span(), "0"), (source_span(), True)):
        with pytest.raises(LclValidationError):
            cast(Any, ConfigImport)("a.lclcfg", span, ordinal, "a")


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ['choice: "missing"\n', "choice: NEED_OVERRIDE\n"])
async def test_imported_dynamic_targets_cannot_read_importer_definitions(prefix: str) -> None:
    """A named import has its own chronological target-selection context."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text(prefix + 'import "part.lclcfg" as m\n', encoding="utf-8")
        (root / "part.lclcfg").write_text('using f"{choice}.lclcfg"\n', encoding="utf-8")
        with pytest.raises(LclConfigUsingError) as caught:
            await load_config(root / "main.lclcfg")
        assert "choice" in str(caught.value)
        assert len(caught.value.config_stack) == 3


@pytest.mark.asyncio
async def test_nested_imports_targets_merging_history_and_magic() -> None:
    """Every occurrence qualifies once, retains child origins, and merges chronologically."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        sources = {
            "main.lclcfg": (
                'profile: "part"\nimport f"{profile}.lclcfg" as services.db\n'
                'import "patch.lclcfg" as services.db\n'
            ),
            "part.lclcfg": (
                'x: 2\nusing "shared.lclcfg"\nimport "nested.lclcfg" as nested\n'
                "y: x + nested.z\n"
            ),
            "shared.lclcfg": "file: __file__\n",
            "nested.lclcfg": "z: 3\n",
            "patch.lclcfg": "x: 10\n",
        }
        for name, text in sources.items():
            (root / name).write_text(text, encoding="utf-8")
        config = await load_config(root / "main.lclcfg")
        assert config.namespace_names == frozenset({"services.db", "services.db.nested"})
        assert len(config.history["services.db.x"]) == 2
        async with config.to_frame() as frame:
            assert await frame.get("services.db.y") == 13
            assert await frame.get("services.db.file") == str(root / "shared.lclcfg")


@pytest.mark.asyncio
async def test_loader_overrides_reach_imported_dynamic_dependencies() -> None:
    """Explicit call overrides satisfy placeholders and affect target dependants."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        sources = {
            "main.lclcfg": 'import "part.lclcfg" as m\n',
            "part.lclcfg": 'profile: NEED_OVERRIDE\nchoice: profile\nusing f"{choice}.lclcfg"\n',
            "chosen.lclcfg": "result: 42\n",
        }
        for name, text in sources.items():
            (root / name).write_text(text, encoding="utf-8")
        config = await load_config(root / "main.lclcfg", overrides={"profile": "chosen"})
        async with config.to_frame() as frame:
            assert await frame.get("m.result") == 42
            with pytest.raises(LclEvaluationError, match="m.profile needs a value"):
                await frame.get("m.profile")


@pytest.mark.asyncio
@pytest.mark.parametrize("child", ["", "a: 1\na.b: 2\n"])
async def test_empty_namespace_and_invalid_child_cannot_be_repaired_by_importer(child: str) -> None:
    """Empty imports reserve names and child validation precedes parent replacement."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text(
            'import "part.lclcfg" as m\nm.a: FRAME_PROXY\n', encoding="utf-8"
        )
        (root / "part.lclcfg").write_text(child, encoding="utf-8")
        if child:
            with pytest.raises(LclValidationError, match="conflict"):
                await load_config(root / "main.lclcfg")
        else:
            config = await load_config(root / "main.lclcfg")
            with pytest.raises(LclValidationError, match="namespace"):
                config.to_frame(preset={"m": 42})


@pytest.mark.asyncio
async def test_optional_import_retries_and_nested_missing_remains_an_error() -> None:
    """Missing snapshots are not cached, and optionality stops at the direct target."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "main.lclcfg").write_text('import? "part.lclcfg" as m\n', encoding="utf-8")
        loader = ConfigLoader(FileConfigResolver())
        assert (await loader.load(root / "main.lclcfg")).namespace_names == frozenset()
        (root / "part.lclcfg").write_text('using "required.lclcfg"\n', encoding="utf-8")
        with pytest.raises(LclConfigUsingError) as caught:
            await loader.load(root / "main.lclcfg")
        assert isinstance(caught.value.__cause__, FileNotFoundError)
        assert len(caught.value.config_stack) == 3
        (root / "required.lclcfg").write_text("x: 42\n", encoding="utf-8")
        config = await loader.load(root / "main.lclcfg")
        async with config.to_frame() as frame:
            assert await frame.get("m.x") == 42


@pytest.mark.asyncio
async def test_import_cycle_is_independent_of_alias_and_parallel_error_paths() -> None:
    """Aliases do not evade file cycles, and concurrent callers retain separate paths."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name in ("left", "right"):
            (root / f"{name}.lclcfg").write_text('import "part.lclcfg" as m\n', encoding="utf-8")
        (root / "part.lclcfg").write_text("x: (\n", encoding="utf-8")
        loader = ConfigLoader(FileConfigResolver())
        failures = await asyncio.gather(
            loader.load(root / "left.lclcfg"),
            loader.load(root / "right.lclcfg"),
            return_exceptions=True,
        )
        assert all(isinstance(error, LclConfigSyntaxError) for error in failures)
        left, right = failures
        assert isinstance(left, LclConfigSyntaxError) and isinstance(right, LclConfigSyntaxError)
        assert left is not right
        assert "left.lclcfg" in str(left) and "right.lclcfg" not in str(left)
        assert "right.lclcfg" in str(right) and "left.lclcfg" not in str(right)
        (root / "part.lclcfg").write_text('import "part.lclcfg" as other\n', encoding="utf-8")
        with pytest.raises(LclConfigCycleError):
            await loader.load(root / "left.lclcfg")
