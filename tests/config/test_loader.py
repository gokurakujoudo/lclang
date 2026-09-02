"""Behavioural tests for source-ordered `using` expansion."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.ast import LclConstant
from lclang.config import (
    ConfigLoader,
    ConfigLoadLimits,
    ConfigUsing,
    LclConfigCycleError,
    LclConfigLimitError,
    LclConfigUsingError,
    ResolvedConfigSource,
    load_config,
    parse_config,
)
from lclang.config.errors import LclConfigSyntaxError
from lclang.config.sources import LoadedConfigSource
from lclang.config.using import evaluate_using_target, snapshot_using_overrides
from lclang.lang import parse_expression
from tests.config.support import MappingResolver


@pytest.mark.asyncio
async def test_nested_using_binds_file_magic_to_each_physical_source() -> None:
    """Every nested definition receives its own canonical physical file path."""
    with TemporaryDirectory(prefix="lclang-nested-magic-") as directory:
        root = Path(directory)
        first = root / "a.lclcfg"
        second = root / "b.lclcfg"
        third = root / "c.lclcfg"
        third.write_text("z: __file__\n", encoding="utf-8")
        second.write_text('using "c.lclcfg"\ny: __file__\n', encoding="utf-8")
        first.write_text('using "b.lclcfg"\nx: __file__\n', encoding="utf-8")

        config = await load_config(first)

        values: dict[str, object] = {}
        for name in ("x", "y", "z"):
            expression = config.definitions[name].expression
            assert isinstance(expression, LclConstant)
            values[name] = expression.value
        assert values == {
            "x": str(first.resolve()),
            "y": str(second.resolve()),
            "z": str(third.resolve()),
        }
        assert len(set(values.values())) == 3


@pytest.mark.asyncio
async def test_nested_using_expands_in_place_with_history_and_magic(tmp_path: Path) -> None:
    """Nested files expand at their use sites and later declarations win globally."""
    shared = tmp_path / "shared.lclcfg"
    child_dir = tmp_path / "nested"
    child_dir.mkdir()
    child = child_dir / "child.lclcfg"
    root = tmp_path / "root.lclcfg"
    shared.write_text("value: 2\n", encoding="utf-8")
    child.write_text(
        "using \"__dir__/../shared.lclcfg\"\n"
        "origin: __file__\n"
        "value: 3\n",
        encoding="utf-8",
    )
    root.write_text(
        "value: 1\nusing \"nested/child.lclcfg\"\nresult: value + 1\nvalue: 4\n",
        encoding="utf-8",
    )

    config = await load_config(root)

    assert list(config.definitions) == ["value", "origin", "result"]
    assert len(config.history["value"]) == 4
    assert isinstance(config.definitions["origin"].expression, LclConstant)
    assert config.definitions["origin"].expression.value == str(child.resolve())
    assert config.definitions["value"] is config.history["value"][-1]


@pytest.mark.asyncio
async def test_dynamic_using_observes_prior_winners_and_typed_overrides(
    tmp_path: Path,
) -> None:
    """Each f-string target gets fresh source-order state beneath overrides."""
    root = (tmp_path / "root.lclcfg").resolve()
    first = (tmp_path / "first.lclcfg").resolve()
    second = (tmp_path / "second.lclcfg").resolve()
    override = (tmp_path / "base-override.lclcfg").resolve()
    texts = {
        root: (
            'base: "base"\n'
            'part: "first"\n'
            'using f"{part}.lclcfg"\n'
            'part: "second"\n'
            'using f"{part}.lclcfg"\n'
        ),
        first: 'selected: "first"\n',
        second: 'selected: "second"\n',
        override: 'selected: "override"\n',
    }
    ordinary = await ConfigLoader(MappingResolver(texts)).load(root)
    selected = [item.expression for item in ordinary.history["selected"]]
    assert all(isinstance(item, LclConstant) for item in selected)
    assert [item.value for item in selected if isinstance(item, LclConstant)] == [
        "first",
        "second",
    ]

    overridden = await ConfigLoader(MappingResolver(texts)).load(
        root,
        overrides={"part": parse_expression("base + '-override'")},
    )
    assert len(overridden.history["selected"]) == 2
    winner = overridden.definitions["selected"].expression
    assert isinstance(winner, LclConstant)
    assert winner.value == "override"


@pytest.mark.asyncio
async def test_dynamic_using_supports_env_and_reports_position_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment targets work while unavailable or invalid results stay structured."""
    root = (tmp_path / "root.lclcfg").resolve()
    child = (tmp_path / "chosen.lclcfg").resolve()
    override_child = (tmp_path / "override.lclcfg").resolve()
    monkeypatch.setenv("LCLANG_USING_PART", "chosen")
    resolver = MappingResolver(
        {
            root: 'using f"{env.LCLANG_USING_PART}.lclcfg"\n',
            child: "value: 42\n",
            override_child: "value: 84\n",
        }
    )
    config = await ConfigLoader(resolver).load(root)
    value = config.definitions["value"].expression
    assert isinstance(value, LclConstant)
    assert value.value == 42

    overridden = await ConfigLoader(resolver).load(
        root,
        overrides={"env.LCLANG_USING_PART": "override"},
    )
    overridden_value = overridden.definitions["value"].expression
    assert isinstance(overridden_value, LclConstant)
    assert overridden_value.value == 84

    for source, message in (
        ('using f"{later}.lclcfg"\nlater: "chosen"\n', "unknown variable"),
        ('using f"{\'\'}"\n', "non-empty"),
        ('using f"{\'chosen.txt\'}"\n', ".lclcfg"),
    ):
        with pytest.raises(LclConfigUsingError, match=message) as caught:
            await ConfigLoader(MappingResolver({root: source})).load(root)
        assert caught.value.span is not None
        assert caught.value.span.start.line == 1


@pytest.mark.asyncio
async def test_dynamic_using_validates_overrides_masks_and_evaluated_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loader override validation and defensive target checks remain structured."""
    with pytest.raises(TypeError, match="mapping"):
        snapshot_using_overrides(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="names"):
        snapshot_using_overrides({1: "value"})  # type: ignore[dict-item]

    root = (tmp_path / "root.lclcfg").resolve()
    child = (tmp_path / "chosen.lclcfg").resolve()
    resolver = MappingResolver(
        {
            root: 'part!: "chosen"\nusing f"{part}.lclcfg"\n',
            child: "value: 42\n",
        }
    )
    loaded = await ConfigLoader(resolver).load(
        root,
        overrides={"part!": parse_expression("'chosen'")},
    )
    assert "value" in loaded.definitions

    declaration = parse_config('using f"chosen.lclcfg"\n').declarations[0]
    assert isinstance(declaration, ConfigUsing)

    async def wrong_result(*args: object) -> object:
        return 1

    monkeypatch.setattr("lclang.config.using.evaluate_target_expression", wrong_result)
    with pytest.raises(LclConfigUsingError, match="non-empty text"):
        await evaluate_using_target(declaration, (), {})


@pytest.mark.asyncio
async def test_cycles_missing_files_and_limits_are_structured(tmp_path: Path) -> None:
    """Rainy loading paths report stable configuration failures."""
    first = tmp_path / "first.lclcfg"
    second = tmp_path / "second.lclcfg"
    first.write_text("using \"second.lclcfg\"\n", encoding="utf-8")
    second.write_text("using \"first.lclcfg\"\n", encoding="utf-8")
    with pytest.raises(LclConfigCycleError):
        await load_config(first)

    missing = tmp_path / "missing-root.lclcfg"
    missing.write_text("using \"absent.lclcfg\"\n", encoding="utf-8")
    with pytest.raises(LclConfigUsingError):
        await load_config(missing)

    with pytest.raises(LclConfigLimitError):
        await load_config(first, limits=ConfigLoadLimits(max_sources=1))


@pytest.mark.asyncio
async def test_loader_single_flight_cancellation_retry_and_unique_limits(tmp_path: Path) -> None:
    """Concurrent owners are shielded, failures retry, and every limit is deterministic."""
    root = (tmp_path / "root.lclcfg").resolve()
    resolver = MappingResolver({root: "first: 1\nsecond: 2\n"})
    loader = ConfigLoader(resolver)
    first, second = await asyncio.gather(loader.load(root), loader.load(root))
    assert first.definitions == second.definitions
    assert resolver.calls[root] == 1

    with pytest.raises(LclConfigLimitError, match="character"):
        await ConfigLoader(
            resolver,
            ConfigLoadLimits(max_characters=1),
        ).load(root)
    with pytest.raises(LclConfigLimitError, match="declaration"):
        await ConfigLoader(
            resolver,
            ConfigLoadLimits(max_declarations=1),
        ).load(root)

    child = (tmp_path / "child.lclcfg").resolve()
    nested = MappingResolver({root: 'using "child.lclcfg"\n', child: "value: 1\n"})
    with pytest.raises(LclConfigLimitError, match="depth"):
        await ConfigLoader(nested, ConfigLoadLimits(max_depth=1)).load(root)


@pytest.mark.asyncio
async def test_waiter_cancellation_does_not_cancel_shared_owner(tmp_path: Path) -> None:
    """One cancelled waiter leaves the source owner available to its peer."""
    root = (tmp_path / "slow.lclcfg").resolve()
    started = asyncio.Event()
    release = asyncio.Event()

    class SlowResolver:
        """Hold one source request until the test releases it."""

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Wait for release and return one valid source."""
            del importer
            started.set()
            await release.wait()
            return ResolvedConfigSource("slow", "slow", path, "value: 1\n")

    loader = ConfigLoader(SlowResolver())
    cancelled = asyncio.create_task(loader.load(root))
    peer = asyncio.create_task(loader.load(root))
    await started.wait()
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    release.set()
    assert "value" in (await peer).definitions


@pytest.mark.asyncio
async def test_failed_owner_retries_and_config_errors_are_not_rewrapped(tmp_path: Path) -> None:
    """Failed attempts leave no poisoned task while structured parser failures survive."""
    root = (tmp_path / "retry.lclcfg").resolve()

    class FlakyResolver:
        """Fail the first retrieval and succeed on retry."""

        def __init__(self) -> None:
            """Initialize the attempt counter."""
            self.calls = 0

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Raise an OS error once before returning valid text."""
            del importer
            self.calls += 1
            if self.calls == 1:
                raise OSError("temporary")
            return ResolvedConfigSource("retry", "retry", path, "value: 1\n")

    resolver = FlakyResolver()
    loader = ConfigLoader(resolver)
    with pytest.raises(LclConfigUsingError):
        await loader.load(root)
    assert "value" in (await loader.load(root)).definitions

    class StructuredResolver:
        """Raise one already-structured configuration error."""

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Raise the stable test error without wrapping."""
            del path, importer
            raise LclConfigSyntaxError("structured")

    with pytest.raises(LclConfigSyntaxError, match="structured"):
        await ConfigLoader(StructuredResolver()).load(root)

    class AliasResolver:
        """Return one stable identity for two requested paths."""

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Return valid text under a shared identity."""
            del importer
            return ResolvedConfigSource("alias", str(path), path, "value: 1\n")

    alias_loader = ConfigLoader(AliasResolver())
    one = await alias_loader.source_for(root, None)
    two = await alias_loader.source_for((tmp_path / "alias.lclcfg").resolve(), None)
    assert one is two


@pytest.mark.asyncio
async def test_owner_cancellation_is_removed_and_retries(tmp_path: Path) -> None:
    """A cancelled source owner does not poison the loader's task cache."""
    root = (tmp_path / "owner-cancel.lclcfg").resolve()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class OwnerResolver:
        """Expose the resolver owner so the test can cancel its task."""

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Block the first attempt and allow the retry to complete."""
            nonlocal calls
            del importer
            calls += 1
            started.set()
            await release.wait()
            return ResolvedConfigSource("owner", "owner", path, "value: 1\n")

    loader = ConfigLoader(OwnerResolver())
    waiter = asyncio.create_task(loader.source_for(root, None))
    await started.wait()
    loader.tasks[root].cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    assert (await loader.source_for(root, None)).document.declarations
    assert calls == 2


@pytest.mark.asyncio
async def test_failed_former_owner_does_not_remove_replacement_task(tmp_path: Path) -> None:
    """A failing source owner cannot delete a newer task installed for the same path."""
    root = (tmp_path / "replacement.lclcfg").resolve()
    replacement: asyncio.Task[LoadedConfigSource] | None = None
    blocker = asyncio.Event()

    async def replacement_owner() -> LoadedConfigSource:
        """Remain pending until the test cancels the synthetic replacement."""
        await blocker.wait()
        raise AssertionError("replacement should be cancelled")

    class ReplacingResolver:
        """Replace the loader cache entry before failing the former owner."""

        loader: ConfigLoader

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Install a new owner task and raise a structured failure."""
            nonlocal replacement
            del importer
            replacement = asyncio.create_task(replacement_owner())
            self.loader.tasks[path] = replacement
            raise LclConfigSyntaxError("former owner failed")

    resolver = ReplacingResolver()
    loader = ConfigLoader(resolver)
    resolver.loader = loader
    with pytest.raises(LclConfigSyntaxError, match="former owner failed"):
        await loader.source_for(root, None)
    assert replacement is not None
    assert loader.tasks[root] is replacement
    replacement.cancel()
    with pytest.raises(asyncio.CancelledError):
        await replacement


def test_loader_rejects_cross_loop_reuse(tmp_path: Path) -> None:
    """A loader binds to its first event loop even after successful completion."""
    root = (tmp_path / "loop.lclcfg").resolve()
    loader = ConfigLoader(MappingResolver({root: "value: 1\n"}))
    asyncio.run(loader.load(root))
    with pytest.raises(Exception, match="cross event loops"):
        asyncio.run(loader.load(root))
