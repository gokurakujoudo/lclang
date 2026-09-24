"""Lowest-priority defaults retain lexical lookup, snapshots and single-flight results."""

import asyncio
from typing import cast

import pytest

import lclang
from lclang.defaults import DefaultBinding
from lclang.runtime.frame.defaults import create_default_frame, default_scope


def test_binding_rejects_non_callable_factory() -> None:
    """CLI declaration snapshots cannot retain an invalid factory."""
    with pytest.raises(TypeError, match="callable"):
        DefaultBinding(factory=3)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_default_scope_names_masks_and_real_prefix_shadowing() -> None:
    """Partial config scopes see default leaves while concrete parents suppress them."""
    bindings = {"settings.limit!": DefaultBinding(3), "settings.mode": DefaultBinding("safe")}
    async with create_default_frame(bindings) as defaults, lclang.define_frame() as frame:
        with default_scope(frame, defaults):
            assert frame.is_masked("settings.limit")
            scope = cast(lclang.FrameProxy, await frame.get("settings"))
            assert set(await scope.field_names()) == {"limit", "mode"}
            assert await scope.get("limit") == 3
            frame.mixin({"settings.mode": "fast"})
            assert await scope.get("mode") == "fast"
            assert await scope.get("limit") == 3
        assert not frame.has("settings.limit")
    async with (
        create_default_frame(bindings) as defaults,
        lclang.define_frame(
            preset={"settings": object()},
        ) as frame,
    ):
        with default_scope(frame, defaults):
            assert not frame.has("settings.limit")
            with pytest.raises(lclang.LclNameError):
                await frame.get("settings.limit")


@pytest.mark.asyncio
async def test_factory_failure_shared_and_new_execution_retries() -> None:
    """Concurrent readers share the cached failure and each new run gets a fresh attempt."""
    calls = 0

    async def fail() -> object:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        raise ValueError("factory failure")

    async with lclang.define_frame() as frame:
        for expected in (1, 2):
            async with create_default_frame({"value": DefaultBinding(factory=fail)}) as defaults:
                with default_scope(frame, defaults):
                    errors = await asyncio.gather(
                        frame.get("value"),
                        frame.get("value"),
                        return_exceptions=True,
                    )
                    assert isinstance(errors[0], Exception) and errors[0] is errors[1]
                    with pytest.raises(type(errors[0])) as caught:
                        await frame.get("value")
                    assert caught.value is errors[0]
                    assert calls == expected


@pytest.mark.asyncio
async def test_cached_dependencies_remain_snapshots_across_default_scopes() -> None:
    """A borrowed Frame's existing calculations are neither invalidated nor rebound."""
    module = lclang.define_module("config", {"double": "value * 2"})
    async with lclang.define_frame(module) as frame:
        for value in (3, 7):
            async with create_default_frame({"value": DefaultBinding(value)}) as defaults:
                with default_scope(frame, defaults):
                    assert await frame.get("value") == value
                    assert await frame.get("double") == 6
        assert await frame.get("double") == 6
