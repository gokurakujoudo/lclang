"""Deterministic scale tests for configuration parsing and loading."""

import asyncio
from pathlib import Path

import pytest

from lclang.config import (
    Config,
    ConfigLoader,
    ConfigLoadLimits,
    ResolvedConfigSource,
    parse_config,
)
from tests.config.support import MappingResolver


def test_ten_thousand_definitions_parse_iteratively(tmp_path: Path) -> None:
    """Large flat documents retain exact first and last declaration positions."""
    text = "".join(f"value_{index}: {index}\n" for index in range(10_000))
    document = parse_config(text, source_path=tmp_path / "large.lclcfg")
    assert len(document.declarations) == 10_000
    assert document.declarations[0].span.start.line == 1
    assert document.declarations[-1].span.start.line == 10_000


@pytest.mark.asyncio
async def test_two_hundred_sources_and_one_hundred_callers_are_deterministic(
    tmp_path: Path,
) -> None:
    """A deep graph caches unique sources and concurrent roots share one owner."""
    paths = [(tmp_path / f"source-{index}.lclcfg").resolve() for index in range(200)]
    texts = {
        path: (
            f'using "source-{index + 1}.lclcfg"\nvalue_{index}: {index}\n'
            if index < 199
            else "value_199: 199\n"
        )
        for index, path in enumerate(paths)
    }
    resolver = MappingResolver(texts)
    loader = ConfigLoader(resolver, ConfigLoadLimits(max_depth=200))
    configs = await asyncio.gather(*(loader.load(paths[0]) for _ in range(100)))
    assert all(config.definitions == configs[0].definitions for config in configs)
    assert len(configs[0].definitions) == 200
    assert sum(resolver.calls.values()) == 200


@pytest.mark.asyncio
async def test_one_hundred_waiters_allow_half_to_cancel(tmp_path: Path) -> None:
    """Cancelling half the waiters leaves one shared source owner and peers."""
    root = (tmp_path / "shared.lclcfg").resolve()
    gate = asyncio.Event()
    calls = 0

    class GatedResolver:
        """Hold the unique request until all waiters are queued."""

        async def resolve(
            self,
            path: Path,
            *,
            importer: ResolvedConfigSource | None,
        ) -> ResolvedConfigSource:
            """Count one request, wait, and return valid text."""
            nonlocal calls
            del importer
            calls += 1
            await gate.wait()
            return ResolvedConfigSource("shared", "shared", path, "value: 1\n")

    loader = ConfigLoader(GatedResolver())
    tasks = [asyncio.create_task(loader.load(root)) for _ in range(100)]
    await asyncio.sleep(0)
    for task in tasks[:50]:
        task.cancel()
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert sum(isinstance(result, asyncio.CancelledError) for result in results) == 50
    for result in results[50:]:
        assert isinstance(result, Config)
        assert "value" in result.definitions
    assert calls == 1


@pytest.mark.asyncio
async def test_one_hundred_config_frames_keep_concurrent_snapshots_isolated(tmp_path: Path) -> None:
    """One Config creates separate caches while each Frame shares its own flight."""
    path = (tmp_path / "frames.lclcfg").resolve()
    config = await ConfigLoader(MappingResolver({path: "result: int(offset) + produce()\n"})).load(
        path
    )
    calls = [0] * 100

    async def run(index: int) -> object:
        """Evaluate one input concurrently through its owned context."""

        async def produce() -> int:
            """Allow peer tasks to join one Frame's lazy computation."""
            calls[index] += 1
            await asyncio.sleep(0)
            return 1

        async with config.to_frame(preset={"offset": str(index), "produce": produce}) as frame:
            values = await asyncio.gather(*(frame.get("result") for _ in range(10)))
            assert values == [index + 1] * 10
        assert frame.closed
        return values[0]

    assert await asyncio.gather(*(run(index) for index in range(100))) == list(range(1, 101))
    assert calls == [1] * 100
