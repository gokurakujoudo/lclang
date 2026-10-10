"""Optional imports retain direct-read boundaries and complete loading diagnostics."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from lclang.config import (
    ConfigDefinition,
    ConfigLoader,
    FileConfigResolver,
    LclConfigSyntaxError,
    load_config,
    parse_config,
)
from lclang.errors import LclError, LclSyntaxError
from lclang.lang.lexer import scan_tokens
from lclang.lang.lexer.fstring_values import FStringField
from lclang.lang.parser.fstrings import internal_convert_part
from tests.config.support import source_span


@pytest.mark.parametrize("source", ['import "bad.lclcfg" as m @', 'import "unterminated'])
def test_import_lexical_failures_keep_source(source: str) -> None:
    """Alias and target lexing failures remain config syntax errors with snapshots."""
    with pytest.raises(LclConfigSyntaxError) as failure:
        parse_config(source)
    assert failure.value.span is not None
    assert failure.value.span.snapshot is not None
    assert failure.value.span.snapshot.text == source


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"\xff", b"value: (", b'using "missing.lclcfg"'])
async def test_optional_import_does_not_hide_existing_file_errors(payload: bytes) -> None:
    """Encoding, syntax, and nested required absence cannot mean optional absence."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        main = root / "main.lclcfg"
        main.write_text('import? f"{__dir__}/child.lclcfg" as m', encoding="utf-8")
        (root / "child.lclcfg").write_bytes(payload)
        with pytest.raises(Exception) as failure:
            await load_config(main)
        assert "Error in loading config file" in str(failure.value)
        assert "import?" in str(failure.value)
        assert "child.lclcfg" in str(failure.value)


@pytest.mark.asyncio
async def test_required_and_optional_imports_share_read_but_not_outcome() -> None:
    """The same missing child fails a required waiter and skips an optional waiter."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        required, optional = root / "required.lclcfg", root / "optional.lclcfg"
        required.write_text('import "child.lclcfg" as m', encoding="utf-8")
        optional.write_text('before: 1\nimport? "child.lclcfg" as m\nafter: 2', encoding="utf-8")
        loader = ConfigLoader(FileConfigResolver())
        failed, config = await asyncio.gather(
            loader.load(required), loader.load(optional), return_exceptions=True
        )
        assert isinstance(failed, Exception)
        assert not isinstance(config, BaseException)
        assert list(config.definitions) == ["before", "after"]
        assert config.namespace_names == frozenset()
        (root / "child.lclcfg").write_text("x: 3", encoding="utf-8")
        loaded = await loader.load(required)
        assert list(loaded.definitions) == ["m.x"]


@pytest.mark.asyncio
async def test_direct_expansion_compatibility_and_native_structure_failure() -> None:
    """The existing expand entry remains usable; native structural failures retain class."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        main = root / "main.lclcfg"
        main.write_text("x: 1", encoding="utf-8")
        loader = ConfigLoader(FileConfigResolver())
        loaded = await loader.source_for(main, None)
        output: list[ConfigDefinition] = []
        await loader.expand(loaded, (), 1, output, {})
        assert [str(item.name) for item in output] == ["x"]
        main.write_text('m: 1\nimport "empty.lclcfg" as m', encoding="utf-8")
        (root / "empty.lclcfg").write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="namespace") as failure:
            await load_config(main)
        assert type(failure.value) is ValueError
        assert "main.lclcfg" in str(failure.value)


def test_lexical_spanless_failure_and_manual_fstring_retain_error_contract() -> None:
    """Custom lexical services and source-less token values do not invent snapshots."""
    failure = LclSyntaxError("custom scanner failure")
    with (
        patch("lclang.lang.lexer.scanner.InternalScanner.scan", side_effect=failure),
        pytest.raises(LclSyntaxError) as caught,
    ):
        scan_tokens("x")
    assert caught.value is failure
    assert caught.value.span is None
    part = FStringField("1 + 2", expression_offset=0)
    converted = internal_convert_part(part, source_span())
    assert converted.span.snapshot is None


@pytest.mark.asyncio
async def test_dynamic_missing_name_hides_generated_target_but_keeps_user_owner() -> None:
    """A missing field has physical coordinates without exposing a loader binding."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        source = 'using f"{__dir__}/profiles/{missing}.lclcfg"\r\n'
        path.write_text(source, encoding="utf-8", newline="")
        with pytest.raises(Exception) as failure:
            await load_config(path)
        assert "using_target" not in str(failure.value)
        cause = failure.value.__cause__
        assert isinstance(cause, LclError)
        assert cause.span is not None
        assert cause.span.start.column == source.index("missing") + 1
        assert cause.span.snapshot is not None
        assert cause.span.snapshot.text == source
        source = 'using_target: NEED_OVERRIDE\nusing f"{__dir__}/{using_target}.lclcfg"'
        path.write_text(source, encoding="utf-8")
        with pytest.raises(Exception) as user_failure:
            await load_config(path)
        assert "Error in evaluating using_target [LCL3001]" in str(user_failure.value)
