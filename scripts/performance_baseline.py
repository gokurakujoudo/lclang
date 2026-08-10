"""Produce the informational lclang performance baseline as stable JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import tracemalloc
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import TypedDict

# Make the checked-out package importable without installation or ``PYTHONPATH``.
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import lclang  # noqa: E402
from lclang.config import ConfigLoader, ResolvedConfigSource  # noqa: E402
from lclang.runtime import build_dependency_graph, topological_order  # noqa: E402


class Measurement(TypedDict):
    """Describe one repeated benchmark measurement."""

    operations: int
    median_seconds: float
    operations_per_second: float


class BaselineReport(TypedDict):
    """Describe the versioned JSON baseline document."""

    schema: int
    python: str
    lclang: str
    platform: str
    implementation: str
    executable: str
    workload: int
    repetitions: int
    warmups: int
    peak_traced_bytes: int
    metrics: dict[str, Measurement]


class MemoryConfigResolver:
    """Return one immutable configuration source without filesystem I/O."""

    async def resolve(
        self,
        path: Path,
        *,
        importer: ResolvedConfigSource | None,
    ) -> ResolvedConfigSource:
        """Resolve *path* to a deterministic in-memory configuration."""
        del importer
        return ResolvedConfigSource(str(path), str(path), path, "result: 1 + 2\n")


def measure(
    operation: Callable[[], object],
    operations: int,
    repetitions: int,
    warmups: int,
) -> Measurement:
    """Measure a fixed operation batch after unrecorded warm-up runs."""
    for _ in range(warmups):
        operation()
    elapsed: list[float] = []
    for _ in range(repetitions):
        started = perf_counter()
        operation()
        elapsed.append(perf_counter() - started)
    middle = median(elapsed)
    return {
        "operations": operations,
        "median_seconds": middle,
        "operations_per_second": operations / middle if middle else 0.0,
    }


def benchmark_operations(workload: int) -> dict[str, Callable[[], object]]:
    """Build deterministic operation batches for every published metric."""
    source = "([1, 2, 3][1] + 4) * 2"
    parsed = lclang.parse_expression(source)
    module = lclang.define_module("benchmark", {"value": "base + 1"})
    graph_definitions = {
        f"n{index}": "0" if index == 0 else f"n{index - 1} + 1"
        for index in range(workload)
    }
    config_path = Path.cwd() / "benchmark.lclcfg"

    async def cold_lookup() -> None:
        for _ in range(workload):
            frame = lclang.Frame(module, values={"base": 1})
            try:
                await frame.get("value")
            finally:
                await frame.close()

    async def hot_lookup() -> None:
        frame = lclang.Frame(module, values={"base": 1})
        try:
            await frame.get("value")
            for _ in range(workload):
                await frame.get("value")
        finally:
            await frame.close()

    async def recalculate() -> None:
        frame = lclang.Frame(module, values={"base": 1})
        try:
            await frame.get("value")
            for _ in range(workload):
                await frame.recalculate("value")
        finally:
            await frame.close()

    async def config_load() -> None:
        for _ in range(workload):
            await ConfigLoader(MemoryConfigResolver()).load(config_path)

    return {
        "parse": lambda: [lclang.parse_expression(source) for _ in range(workload)],
        "canonical_round_trip": lambda: [
            lclang.parse_expression(lclang.to_source(parsed)) for _ in range(workload)
        ],
        "standalone_evaluate": lambda: [
            lclang.evaluate_sync(parsed) for _ in range(workload)
        ],
        "frame_cold_lookup": lambda: asyncio.run(cold_lookup()),
        "frame_hot_lookup": lambda: asyncio.run(hot_lookup()),
        "frame_recalculate": lambda: asyncio.run(recalculate()),
        "dependency_graph": lambda: topological_order(
            build_dependency_graph(lclang.define_module("graph", graph_definitions))
        ),
        "config_load": lambda: asyncio.run(config_load()),
    }


def validate_controls(workload: int, repetitions: int, warmups: int) -> None:
    """Reject invalid counts before constructing any benchmark workload."""
    if type(workload) is not int or workload <= 0:
        raise ValueError("workload must be a positive integer")
    if type(repetitions) is not int or repetitions <= 0:
        raise ValueError("repetitions must be a positive integer")
    if type(warmups) is not int or warmups < 0:
        raise ValueError("warmups must be a non-negative integer")


def run_baseline(
    workload: int = 100,
    repetitions: int = 5,
    warmups: int = 1,
) -> BaselineReport:
    """Run every informational metric and return its stable JSON-ready report."""
    validate_controls(workload, repetitions, warmups)
    operations = benchmark_operations(workload)
    tracemalloc.start()
    try:
        metrics = {
            name: measure(operation, workload, repetitions, warmups)
            for name, operation in operations.items()
        }
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {
        "schema": 1,
        "python": platform.python_version(),
        "lclang": lclang.__version__,
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "workload": workload,
        "repetitions": repetitions,
        "warmups": warmups,
        "peak_traced_bytes": peak,
        "metrics": metrics,
    }


def main(arguments: Sequence[str] | None = None) -> int:
    """Parse benchmark controls and print exactly one JSON document."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", type=int, default=100)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    options = parser.parse_args(arguments)
    report = run_baseline(options.workload, options.repetitions, options.warmups)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
