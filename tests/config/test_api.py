"""Integration tests for config-to-runtime conversion."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from lclang import LCL_IMPORTS, LCL_RUNTIME, LclNameError
from lclang.config import evaluate_config, load_config
from lclang.runtime import DependencyKind, Frame, FrameDependencyGraph, build_dependency_graph
from lclang.types import FrameId


@pytest.mark.asyncio
async def test_using_flattens_cross_file_dependencies_into_one_module() -> None:
    """Using adds definitions, not evaluation or a runtime dependency layer."""
    with TemporaryDirectory(prefix="lclang-flat-using-") as directory:
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
        assert [(str(edge.source), str(edge.target), edge.kind) for edge in graph.edges] == [
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
async def test_config_masking_is_sticky_across_expansion_and_overrides(tmp_path: Path) -> None:
    """Any marked occurrence protects the final exact-name winner."""
    child = tmp_path / "child.lclcfg"
    root = tmp_path / "root.lclcfg"
    child.write_text("token!: 'old-secret'\n", encoding="utf-8")
    root.write_text('using "child.lclcfg"\ntoken: "new-secret"\n', encoding="utf-8")
    config = await load_config(root)
    module = config.to_module()
    frame = config.frame_factory().create(values={"token": "host-secret"})
    try:
        assert config.masked_names == frozenset({"token"})
        assert module.masked_names == frozenset({"token"})
        assert frame.is_masked("token") is True
        assert await frame.get("token") == "new-secret"
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
async def test_loaded_config_supports_scopes_markers_and_full_lhs(tmp_path: Path) -> None:
    """Qualified winners become proxies and retain complete definition owners."""
    path = tmp_path / "scoped.lclcfg"
    path.write_text(
        "A: FRAME_PROXY\nA.x: 40\nA.owner: lhs()\nresult: A.x + 2\n",
        encoding="utf-8",
    )
    config = await load_config(path)
    frame = config.frame_factory().create()
    try:
        assert await frame.get("result") == 42
        assert await frame.get("A.owner") == "A.owner"
    finally:
        await frame.close()


@pytest.mark.asyncio
async def test_loaded_config_rejects_final_scoped_conflicts(tmp_path: Path) -> None:
    """Final winners cannot contain a real prefix and descendant."""
    path = tmp_path / "conflict.lclcfg"
    path.write_text("A: 1\nA.x: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="conflict"):
        await load_config(path)


@pytest.mark.asyncio
async def test_config_frames_use_lhs_dates_and_static_hierarchy_analysis() -> None:
    """Config runtime defaults expose root/builtins before any graph evaluation."""
    with TemporaryDirectory(prefix="lclang-config-context-") as directory:
        path = Path(directory) / "context.lclcfg"
        path.write_text(
            'k: {"name": lhs()}\n' 'day: parse_ymd("20240229")\n' "roundtrip: to_ymd(day)\n",
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


@pytest.mark.asyncio
async def test_config_to_frame_preserves_canonical_conversion_and_independent_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The direct shortcut retains provenance, masks, precedence, and lazy state."""
    name = "LCLANG_CONFIG_FRAME_PORT"
    monkeypatch.setenv(name, "99")
    calls = 0

    def produce() -> int:
        """Count only requested named computations."""
        nonlocal calls
        calls += 1
        return calls

    with TemporaryDirectory() as directory:
        child = Path(directory) / "base.lclcfg"
        path = Path(directory) / "settings.lclcfg"
        child.write_text('base: 40\ntoken!: "config-secret"\n', encoding="utf-8")
        path.write_text(
            'using "base.lclcfg"\n'
            f"result: base + int(env.{name}) + len(label)\n"
            "owner: lhs()\ntick: produce()\n",
            encoding="utf-8",
        )
        config = await load_config(path)
        preset: dict[str, object] = {
            "base": 0,
            "token": "host-secret",
            f"env.{name}": "1",
            "label": "x",
            "produce": produce,
        }
        frame = config.to_frame(preset=preset)
        preset.update({f"env.{name}": "9", "label": "changed"})
        assert calls == 0
        assert frame.parent is not None and frame.parent.parent is LCL_RUNTIME
        assert frame.module.definitions["base"] is config.definitions["base"].expression
        async with frame:
            assert await frame.get("result") == 42
            assert await frame.get("tick") == 1
            assert await frame.get("tick") == 1
            assert await frame.get("token") == "config-secret"
            assert frame.is_masked("token")
            assert await frame.get("owner") == "owner"
        assert frame.closed
        async with config.to_frame(preset={"produce": produce}) as second:
            assert await second.get("tick") == 2
            assert second is not frame
        async with config.to_frame() as plain:
            assert plain.parent is LCL_IMPORTS
            assert await plain.get("base") == 40
        assert calls == 2
        assert os.environ[name] == "99"


@pytest.mark.asyncio
async def test_config_to_frame_closes_owned_results_after_evaluation_failure() -> None:
    """An async-with shortcut drains cached resources when a later lookup fails."""
    events: list[str] = []

    async def close_resource() -> None:
        """Record successful asynchronous cleanup."""
        events.append("closed")

    resource = SimpleNamespace(aclose=close_resource)

    def create_resource() -> SimpleNamespace:
        """Return a caller-supplied resource only after its definition is requested."""
        events.append("created")
        return resource

    with TemporaryDirectory() as directory:
        path = Path(directory) / "resources.lclcfg"
        path.write_text("resource: create_resource()\nfailure: unknown\n", encoding="utf-8")
        config = await load_config(path)
        frame = config.to_frame(preset={"create_resource": create_resource})
        assert events == []
        with pytest.raises(LclNameError, match="unknown variable: unknown") as failure:
            async with frame:
                assert await frame.get("resource") is resource
                assert await frame.get("resource") is resource
                await frame.get("failure")
        assert failure.value.variable_stack == ("failure",)
        assert frame.closed
        assert events == ["created", "closed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("preset", "error"),
    (([], TypeError), ({1: 2}, TypeError), ({"": 2}, ValueError), ({"A": 1, "A.x": 2}, ValueError)),
)
async def test_config_to_frame_retains_preset_validation(
    preset: object,
    error: type[Exception],
) -> None:
    """Untyped callers receive the same dictionary and binding validation."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "settings.lclcfg"
        path.write_text("result: 42\n", encoding="utf-8")
        config = await load_config(path)
        with pytest.raises(error):
            config.to_frame(preset=preset)  # type: ignore[arg-type]
