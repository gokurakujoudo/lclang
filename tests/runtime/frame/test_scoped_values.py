"""Behavioural contracts for qualified Frame values and proxies."""

import pytest

import lclang
from lclang.runtime import VariableInspectionStatus


@pytest.mark.asyncio
async def test_scoped_definitions_infer_lazy_python_proxies() -> None:
    """Qualified leaves resolve directly and through one caller-bound proxy."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return 21

    module = lclang.define_module(
        "scoped",
        {"A": lclang.FRAME_PROXY, "A.B.x": "produce()", "A.B.y": "A.B.x * 2"},
    )
    async with lclang.define_frame(module, preset={"produce": produce}) as frame:
        proxy = await frame.get("A")
        assert isinstance(proxy, lclang.FrameProxy)
        assert repr(proxy) == "FrameProxy(A)"
        private_name = "_private"
        with pytest.raises(AttributeError, match="_private"):
            getattr(proxy, private_name)
        missing_name = "missing"
        with pytest.raises(AttributeError, match="A.missing"):
            getattr(proxy, missing_name)
        assert await proxy.B.y == 42
        assert await frame.get("A.B.x") == 21
        assert calls == 1
        assert frame.has("A.B")


@pytest.mark.asyncio
async def test_scoped_lookup_uses_caller_hierarchy_and_safe_missing() -> None:
    """A child proxy selects child leaves and falls back to parent leaves."""
    parent = lclang.define_frame(
        lclang.define_module("parent", {"A.parent": "40", "A.optional": "None"})
    )
    child = parent.derive(lclang.define_module("child", {"A.child": "2"}))
    try:
        assert await child.evaluate("A.parent + A.child") == 42
        assert await child.evaluate("A?.missing ?? A.parent") == 40
        with pytest.raises(lclang.LclNameError, match="unknown variable: A.missing"):
            await child.evaluate("A.missing")
        with pytest.raises(lclang.LclNameError, match="unknown variable: missing"):
            await child.evaluate("missing?.value ?? 0")
    finally:
        await child.close()
        await parent.close()


def test_scoped_real_prefix_conflicts_are_eager_and_atomic() -> None:
    """Real ancestors conflict while placeholders and exact overrides work."""
    with pytest.raises(ValueError, match="conflict"):
        lclang.define_module("bad", {"A": "1", "A.x": "2"})
    module = lclang.define_module(
        "good", {"A": lclang.FRAME_PROXY, "A.x": "1", "A.y": "2"}
    )
    parent = lclang.define_frame(module)
    parent.derive(lclang.define_module("child", {"A.x": "3"}))
    with pytest.raises(ValueError, match="conflict"):
        parent.mixin({"A.x.deep": 4})
    assert "A.x.deep" not in parent.values


@pytest.mark.asyncio
async def test_closed_descendants_do_not_block_atomic_parent_mixins() -> None:
    """Only open descendants participate in prospective hierarchy validation."""
    parent = lclang.define_frame()
    child = parent.derive(lclang.define_module("child", {"A": "1"}))
    await child.close()
    parent.mixin({"A.x": 2})
    assert await parent.get("A.x") == 2
    await parent.close()


@pytest.mark.asyncio
async def test_scoped_external_awaitable_is_resolved_lazily() -> None:
    """Host leaves retain the ordinary recursive auto-await boundary."""
    async def value() -> int:
        return 42

    async with lclang.define_frame(preset={"A.B.x": value()}) as frame:
        assert await frame.evaluate("A.B.x") == 42


@pytest.mark.asyncio
async def test_scoped_dependencies_and_inspection_use_qualified_leaf() -> None:
    """Static, dynamic, and inspection evidence names the terminal binding."""
    module = lclang.define_module(
        "evidence", {"A.x": "40", "result": "A.x + 2"}
    )
    async with lclang.define_frame(module) as frame:
        before = frame.dependency_snapshot("result")
        assert [str(edge.target) for edge in before.static_edges] == ["A.x"]
        tree = frame.inspect_variable("result")
        assert [str(item.var_name) for item in tree.dependencies] == ["A.x"]
        assert await frame.get("result") == 42
        after = frame.dependency_snapshot("result")
        assert [str(edge.target) for edge in after.dynamic_edges] == ["A.x"]
        proxy = frame.inspect_variable("A")
        assert proxy.status is VariableInspectionStatus.FRAME_PROXY


@pytest.mark.asyncio
async def test_proxy_operations_reject_recalculation_and_snapshots() -> None:
    """Proxy prefixes are not cached definitions with refreshable evidence."""
    async with lclang.define_frame(
        lclang.define_module("proxy", {"A": lclang.FRAME_PROXY, "A.x": "1"})
    ) as frame:
        with pytest.raises(lclang.LclEvaluationError, match="proxy"):
            await frame.recalculate("A")
        with pytest.raises(lclang.LclEvaluationError, match="proxy"):
            frame.dependency_snapshot("A")
