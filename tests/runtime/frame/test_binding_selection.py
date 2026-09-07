"""Behavior and work bounds for operation-local binding selection."""

from unittest.mock import patch

import pytest

from lclang import define_frame, define_module
from lclang.runtime.frame.binding_lookup import local_binding_kind, select_binding
from lclang.scope_proxy import FrameProxy


@pytest.mark.asyncio
async def test_cached_read_classifies_the_binding_once() -> None:
    """A cached get reuses its initial selection instead of scanning three times."""
    async with define_frame(define_module("lookup", {"answer": "42"})) as frame:
        assert await frame.get("answer") == 42
        with patch(
            "lclang.runtime.frame.binding_lookup.local_binding_kind", wraps=local_binding_kind
        ) as kind:
            assert await frame.get("answer") == 42
            assert kind.call_count == 1


@pytest.mark.asyncio
async def test_selection_retains_owner_path_and_observes_later_mixin() -> None:
    """Selections describe one operation and never stale-cache hierarchy changes."""
    async with (
        define_frame(define_module("parent", {"answer": "42"})) as parent,
        parent.derive(define_module("child", {})) as child,
    ):
        selected = select_binding(child, "answer")
        assert selected.owner is parent
        assert selected.path == (child.frame_id, parent.frame_id)
        child.mixin({"answer": 7})
        assert await child.get("answer") == 7
        assert select_binding(child, "answer").owner is child


@pytest.mark.asyncio
async def test_async_proxy_read_reuses_selection_and_deferred_attributes_stay_live() -> None:
    """Immediate proxy reads scan once; deferred Python attributes read when awaited."""
    async with define_frame(define_module("proxy", {})) as frame:
        frame.mixin({"A.x": 1})
        proxy = await frame.get("A")
        assert isinstance(proxy, FrameProxy)
        with patch(
            "lclang.runtime.frame.binding_lookup.local_binding_kind",
            wraps=local_binding_kind,
        ) as kind:
            assert await proxy.get("x") == 1
            assert kind.call_count == 1
        deferred = proxy.x
        frame.mixin({"A.x": 2})
        assert await deferred == 2
