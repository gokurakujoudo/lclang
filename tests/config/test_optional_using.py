"""Optional source expansion retains required loading and lifecycle contracts."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.config import (
    ConfigLoader,
    ConfigLoadLimits,
    FileConfigResolver,
    ResolvedConfigSource,
    load_config,
)
from lclang.config.config_source import LoadedConfigSource
from lclang.error import (
    LclConfigCycleError,
    LclConfigLimitError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    LclConfigVersionError,
)
from tests.config.support import MappingResolver


@pytest.mark.asyncio
async def test_optional_sources_preserve_precedence_history_magic_and_masks() -> None:
    """Present optional sources expand in place while missing ones contribute nothing."""
    with TemporaryDirectory(prefix="lclang-optional-using-") as directory:
        root = Path(directory)
        (root / "nested").mkdir()
        child = root / "shared.lclcfg"
        child.write_text(
            'value: 2\norigin: __file__\ndirectory: __dir__\ntoken!: "secret"\n',
            encoding="utf-8",
        )
        entry = root / "root.lclcfg"
        entry.write_text(
            'value: 1\nchoice: "shared"\n'
            'using? "absent.lclcfg"\n'
            'using? f"{choice}.lclcfg"\n'
            'using? "__dir__/nested/../shared.lclcfg"\n'
            "value: 3\nresult: value + 1\n",
            encoding="utf-8",
        )
        config = await load_config(entry)
        assert tuple(config.definitions) == (
            "value",
            "choice",
            "origin",
            "directory",
            "token",
            "result",
        )
        assert set(config.history) == set(config.definitions)
        assert len(config.history["value"]) == 4
        assert len(config.history["origin"]) == 2
        assert config.masked_names == frozenset({"token"})
        assert config.history["value"][1].span.origin.path == child.resolve()
        assert config.definitions["value"].span.origin.path == entry.resolve()
        async with config.to_frame() as frame:
            assert await frame.get("result") == 4
            assert await frame.get("origin") == str(child.resolve())
            assert await frame.get("directory") == str(child.resolve().parent)
            assert await frame.get("token") == "secret"


@pytest.mark.asyncio
async def test_missing_optional_sources_retry_without_invalidating_successful_snapshots() -> None:
    """Missing paths retry on reuse while a successfully retrieved child stays cached."""
    with TemporaryDirectory(prefix="lclang-optional-retry-") as directory:
        root = Path(directory)
        entry = root / "root.lclcfg"
        child = root / "local.lclcfg"
        entry.write_text(
            'value: 1\nusing? "local.lclcfg"\nusing? "local.lclcfg"\nresult: value + 1\n',
            encoding="utf-8",
        )
        loader = ConfigLoader(FileConfigResolver())
        initial = await loader.load(entry)
        assert tuple(initial.definitions) == ("value", "result")
        assert len(initial.history["value"]) == 1
        assert child.resolve() not in loader.tasks
        child.write_text("value: 41\n", encoding="utf-8")
        loaded = await loader.load(entry)
        assert len(loaded.history["value"]) == 3
        async with loaded.to_frame() as frame:
            assert await frame.get("result") == 42
        child.write_text("value: 99\n", encoding="utf-8")
        cached = await loader.load(entry)
        async with cached.to_frame() as frame:
            assert await frame.get("result") == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("child_text", "error_type", "message"),
    [
        ("value: (\n", LclConfigSyntaxError, "expression atom"),
        ("__LCL_VERSION__: 2\n", LclConfigVersionError, "unsupported"),
        ('using "absent.lclcfg"\n', LclConfigUsingError, "absent.lclcfg"),
        ('using? "root.lclcfg"\n', LclConfigCycleError, "cycle"),
    ],
)
async def test_existing_optional_source_errors_propagate(
    child_text: str, error_type: type[Exception], message: str
) -> None:
    """An existing child's parser and recursive expansion failures remain visible."""
    with TemporaryDirectory(prefix="lclang-optional-errors-") as directory:
        root = Path(directory)
        entry = root / "root.lclcfg"
        entry.write_text('using? "child.lclcfg"\n', encoding="utf-8")
        (root / "child.lclcfg").write_text(child_text, encoding="utf-8")
        with pytest.raises(error_type, match=message) as caught:
            await load_config(entry)
        if error_type is LclConfigUsingError:
            assert isinstance(caught.value.__cause__, FileNotFoundError)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["directory", "invalid_utf8", "outside_root"])
async def test_optional_filesystem_failures_are_not_absence(kind: str) -> None:
    """Directories, malformed UTF-8, and unauthorized paths remain retrieval errors."""
    with TemporaryDirectory(prefix="lclang-optional-files-") as directory:
        root = Path(directory)
        allowed = root / "allowed"
        allowed.mkdir()
        child = allowed / "child.lclcfg"
        expected: type[Exception]
        if kind == "directory":
            child.mkdir()
            expected = IsADirectoryError
        elif kind == "invalid_utf8":
            child.write_bytes(b"\xff")
            expected = UnicodeDecodeError
        else:
            child = root / "absent-outside.lclcfg"
            expected = PermissionError
        entry = allowed / "root.lclcfg"
        entry.write_text(f'using? "{child.as_posix()}"\n', encoding="utf-8")
        with pytest.raises(LclConfigUsingError) as caught:
            await load_config(entry, resolver=FileConfigResolver(allowed))
        if kind == "invalid_utf8":
            assert isinstance(caught.value.__cause__, expected)
            assert caught.value.code == "LCL321721"
        else:
            assert caught.value.__cause__ is None
            assert caught.value.code == ("LCL321792" if kind == "directory" else "LCL321791")


@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", ["using", "using?"])
@pytest.mark.parametrize(
    ("target", "message"),
    [
        ('f"{later}.lclcfg"', "unknown variable"),
        ("f\"{''}\"", "non-empty"),
        ("f\"{'bad.txt'}\"", ".lclcfg"),
    ],
)
async def test_optional_dynamic_targets_keep_validation(
    keyword: str, target: str, message: str
) -> None:
    """Optional targets still evaluate and validate before attempting retrieval."""
    with TemporaryDirectory(prefix="lclang-optional-target-") as directory:
        entry = Path(directory) / "root.lclcfg"
        entry.write_text(f"  {keyword} {target}\nlater: 'child'\n", encoding="utf-8")
        with pytest.raises(LclConfigUsingError, match=message) as caught:
            await load_config(entry)
        assert caught.value.span is not None
        assert caught.value.span.start.line == 1


@pytest.mark.asyncio
async def test_dynamic_optional_target_observes_overrides_and_missing_file() -> None:
    """A dynamic optional path can be absent or selected through loader overrides."""
    with TemporaryDirectory(prefix="lclang-optional-overrides-") as directory:
        root = Path(directory)
        entry = root / "root.lclcfg"
        entry.write_text(
            'choice: "absent"\nvalue: 1\nusing? f"{choice}.lclcfg"\nresult: value + 1\n',
            encoding="utf-8",
        )
        (root / "chosen.lclcfg").write_text("value: 41\n", encoding="utf-8")
        for overrides, expected in [(None, 2), ({"choice": "chosen"}, 42)]:
            config = await load_config(entry, overrides=overrides)
            async with config.to_frame() as frame:
                assert await frame.get("result") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "limits",
    [
        ConfigLoadLimits(max_sources=1),
        ConfigLoadLimits(max_depth=1),
        ConfigLoadLimits(max_characters=24),
        ConfigLoadLimits(max_declarations=1),
    ],
)
async def test_optional_sources_keep_resource_limits(limits: ConfigLoadLimits) -> None:
    """Optionality does not suppress resource exhaustion in loading or expansion."""
    with TemporaryDirectory(prefix="lclang-optional-limits-") as directory:
        root = Path(directory)
        entry = root / "root.lclcfg"
        entry.write_text('using? "child.lclcfg"\n', encoding="utf-8")
        (root / "child.lclcfg").write_text("value: 42\n", encoding="utf-8")
        with pytest.raises(LclConfigLimitError):
            await load_config(entry, limits=limits)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("absent"),
        PermissionError("denied"),
        OSError("read"),
        KeyError("missing-key"),
        LclConfigSyntaxError("structured"),
        asyncio.CancelledError(),
    ],
)
async def test_custom_resolver_optional_absence_is_explicit(failure: BaseException) -> None:
    """Only FileNotFoundError from direct host retrieval means optional absence."""
    with TemporaryDirectory(prefix="lclang-optional-resolver-") as directory:
        entry = (Path(directory) / "root.lclcfg").resolve()

        class FailingChildResolver(MappingResolver):
            """Inject one failure for the direct child without touching root parsing."""

            async def resolve(
                self, path: Path, *, importer: ResolvedConfigSource | None
            ) -> ResolvedConfigSource:
                """Return the root or raise the supplied retrieval failure."""
                if path != entry:
                    raise failure
                return await super().resolve(path, importer=importer)

        loader = ConfigLoader(FailingChildResolver({entry: 'value: 1\nusing? "child.lclcfg"\n'}))
        if isinstance(failure, FileNotFoundError):
            config = await loader.load(entry)
            async with config.to_frame() as frame:
                assert await frame.get("value") == 1
        elif isinstance(failure, asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await loader.load(entry)
        else:
            with pytest.raises((LclConfigUsingError, LclConfigSyntaxError)) as caught:
                await loader.load(entry)
            if isinstance(failure, LclConfigSyntaxError):
                assert caught.value is not failure
                assert caught.value.message == failure.message
                assert caught.value.code == failure.code
                assert failure.config_stack == ()
                assert len(caught.value.config_stack) == 2
            else:
                assert caught.value.__cause__ is failure


@pytest.mark.asyncio
async def test_concurrent_optional_and_required_requests_share_absence_but_not_policy() -> None:
    """One missing source owner lets an optional caller succeed and a required one fail."""
    with TemporaryDirectory(prefix="lclang-optional-concurrent-") as directory:
        root = await asyncio.to_thread(Path(directory).resolve)
        optional, required, child = (
            root / name for name in ("optional.lclcfg", "required.lclcfg", "child.lclcfg")
        )
        requests: asyncio.Queue[Path] = asyncio.Queue()
        release = asyncio.Event()
        child_calls = 0

        class BlockingMissingResolver(MappingResolver):
            """Hold missing retrieval until both expansion callers have requested it."""

            async def resolve(
                self, path: Path, *, importer: ResolvedConfigSource | None
            ) -> ResolvedConfigSource:
                """Resolve root text or publish one deterministic child absence."""
                nonlocal child_calls
                if path == child:
                    child_calls += 1
                    await release.wait()
                    raise FileNotFoundError(str(path))
                return await super().resolve(path, importer=importer)

        class ObservedLoader(ConfigLoader):
            """Observe requests while retaining the real shared-source coordination."""

            async def source_for(
                self, path: Path, importer: ResolvedConfigSource | None
            ) -> LoadedConfigSource:
                """Signal a request before awaiting the ordinary single-flight result."""
                requests.put_nowait(path)
                return await super().source_for(path, importer)

        loader = ObservedLoader(
            BlockingMissingResolver(
                {
                    optional: 'value: 42\nusing? "child.lclcfg"\n',
                    required: 'using "child.lclcfg"\n',
                }
            )
        )
        optional_task = asyncio.create_task(loader.load(optional))
        required_task = asyncio.create_task(loader.load(required))
        async with asyncio.timeout(5):
            seen = 0
            while seen < 2:
                seen += (await requests.get()) == child
            release.set()
            config = await optional_task
            with pytest.raises(LclConfigUsingError) as caught:
                await required_task
        assert isinstance(caught.value.__cause__, FileNotFoundError)
        assert child_calls == 1
        assert child not in loader.tasks
        async with config.to_frame() as frame:
            assert await frame.get("value") == 42


@pytest.mark.asyncio
async def test_root_and_required_source_absence_remain_errors() -> None:
    """Optional expansion does not change strict root or ordinary using retrieval."""
    with TemporaryDirectory(prefix="lclang-required-absence-") as directory:
        entry = Path(directory) / "root.lclcfg"
        with pytest.raises(LclConfigUsingError) as missing_root:
            await load_config(entry)
        assert isinstance(missing_root.value.__cause__, FileNotFoundError)
        entry.write_text('using "absent.lclcfg"\n', encoding="utf-8")
        with pytest.raises(LclConfigUsingError) as missing_child:
            await load_config(entry)
        assert isinstance(missing_child.value.__cause__, FileNotFoundError)
