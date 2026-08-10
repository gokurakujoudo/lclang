"""Integration tests for config-to-runtime conversion."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.config import evaluate_config, load_config
from lclang.runtime import DependencyKind, Frame, FrameDependencyGraph, build_dependency_graph
from lclang.types import FrameId


@pytest.mark.asyncio
async def test_using_flattens_cross_file_dependencies_into_one_module() -> None:
    """Using adds definitions, not evaluation or a runtime dependency layer."""
    with TemporaryDirectory(prefix="lclang-flat-using-", dir=Path.cwd()) as directory:
        root = Path(directory)
        used = root / "b.lclcfg"
        entry = root / "a.lclcfg"
        used.write_text("z: 200\nw: x * 2\n", encoding="utf-8")
        entry.write_text(
            'x: 100\nusing "b.lclcfg"\ny: z + w\n',
            encoding="utf-8",
        )

        config = await load_config(entry)
        module = config.to_module("flat-using")
        graph = build_dependency_graph(module)

        assert tuple(module.definitions) == ("x", "z", "w", "y")
        assert all(
            module.definitions[name] is config.definitions[name].expression
            for name in module.definitions
        )
        assert tuple(str(name) for name in graph.definitions) == ("x", "z", "w", "y")
        assert graph.external_names == ()
        assert [
            (str(edge.source), str(edge.target), edge.kind)
            for edge in graph.edges
        ] == [
            ("w", "x", DependencyKind.EAGER),
            ("y", "z", DependencyKind.EAGER),
            ("y", "w", DependencyKind.EAGER),
        ]

        frame = Frame(module, FrameId("flat-using"))
        try:
            assert frame.parent is None
            assert await frame.get("x") == 100
            assert await frame.get("z") == 200
            assert await frame.get("w") == 200
            assert await frame.get("y") == 400
        finally:
            await frame.close()


@pytest.mark.asyncio
async def test_loaded_config_builds_independent_runtime_frames(tmp_path: Path) -> None:
    """Final winners form one reusable Module with ordinary forward dependencies."""
    path = tmp_path / "runtime.lclcfg"
    path.write_text("result: base + 1\nbase: 2\n", encoding="utf-8")
    config = await load_config(path)
    factory = config.frame_factory()
    first = factory.create(FrameId("first"))
    second = factory.create(FrameId("second"))
    try:
        assert await first.get("result") == 3
        assert await second.get("result") == 3
    finally:
        await first.close()
        await second.close()
    assert await evaluate_config(config, "result") == 3
    with pytest.raises(TypeError):
        await evaluate_config(object(), "result")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_config_frames_use_lhs_dates_and_static_hierarchy_analysis() -> None:
    """Config runtime defaults expose root/builtins before any graph evaluation."""
    with TemporaryDirectory(prefix="lclang-config-context-", dir=Path.cwd()) as directory:
        path = Path(directory) / "context.lclcfg"
        path.write_text(
            'k: {"name": lhs()}\n'
            'day: parse_ymd("20240229")\n'
            "roundtrip: to_ymd(day)\n",
            encoding="utf-8",
        )
        config = await load_config(path)
        frame = config.frame_factory().create(FrameId("config-context"))
        try:
            graph = build_dependency_graph(frame)
            assert isinstance(graph, FrameDependencyGraph)
            assert frame.parent is not None
            assert graph.external_names == ()
            assert frame.dependency_snapshot("k").dynamic_edges == ()
            assert await frame.get("k") == {"name": "k"}
            assert await frame.get("roundtrip") == "20240229"
        finally:
            await frame.close()
