"""Behavioural tests for live process-environment access."""

import os

import pytest

from lclang.error import LclAttributeError, LclValidationError
from lclang.lang import FrameProxy, define_frame, define_module
from lclang.lang.runtime.frame.environment_proxy import BoundEnvironment
from lclang.utils import env


@pytest.mark.asyncio
async def test_python_identifiers_and_lcl_reserved_names_are_filtered_by_their_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python exposes Unicode identifiers while its Frame adapter removes LCL keywords."""
    monkeypatch.setattr(
        os,
        "environ",
        {"if": "keyword", "FRAME_PROXY": "marker", "LCLANG-NON-IDENTIFIER": "not an attribute"},
    )
    names = env.field_names()
    assert "if" in names and "FRAME_PROXY" in names
    assert "LCLANG-NON-IDENTIFIER" not in names
    async with define_frame() as frame:
        bound_names = await frame.evaluate("env.field_names()")
        assert isinstance(bound_names, list)
        assert "if" not in bound_names and "FRAME_PROXY" not in bound_names
        assert await frame.evaluate("env.get('if')") == "keyword"


@pytest.mark.asyncio
async def test_lcl_environment_falls_back_after_scoped_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frame bindings win without changing live environment fallback values."""
    monkeypatch.setenv("LCLANG_ENV_ALPHA", "system-alpha")
    monkeypatch.setenv("LCLANG_ENV_BETA", "system-beta")
    monkeypatch.delenv("LCLANG_ENV_MISSING", raising=False)
    frame = define_frame(
        define_module(
            "environment",
            {
                "env.LCLANG_ENV_ALPHA": '"module-alpha"',
                "env.LCLANG_ENV_NONE": "None",
                "result": (
                    "env.LCLANG_ENV_ALPHA + ':' + env.LCLANG_ENV_BETA + ':' + "
                    "(env.LCLANG_ENV_MISSING ?? 'fallback')"
                ),
            },
        )
    )
    try:
        environment = await frame.get("env")
        assert type(environment) is BoundEnvironment
        assert repr(environment) == "BoundEnvironment(env)"
        private_name = "__private"
        with pytest.raises(LclAttributeError):
            getattr(environment, private_name)
        with pytest.raises(LclValidationError):
            await environment.get(1)  # type: ignore[arg-type]
        assert await environment.LCLANG_ENV_ALPHA == "module-alpha"
        assert await environment.get("LCLANG_ENV_ALPHA") == "module-alpha"
        assert await environment.get("LCLANG-ENV-INVALID", "fallback") == "fallback"
        assert await environment.get("LCLANG_ENV_NONE", "fallback") is None
        assert await frame.evaluate("env.get('LCLANG_ENV_BETA')") == "system-beta"
        assert await frame.evaluate("env.LCLANG_ENV_BETA") == "system-beta"
        assert await frame.evaluate("env.LCLANG_ENV_ALPHA") == "module-alpha"
        assert await frame.get("result") == "module-alpha:system-beta:fallback"
        names = await environment.field_names()
        assert names == sorted(names)
        assert "LCLANG_ENV_ALPHA" in names
        assert "LCLANG_ENV_BETA" in names
        assert env.LCLANG_ENV_ALPHA == "system-alpha"
    finally:
        await frame.close()


@pytest.mark.asyncio
async def test_environment_overrides_compose_through_presets_and_mixins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preset and mixin leaves override the utility without replacing it."""
    name = "LCLANG_ENV_LAYER_TEST"
    monkeypatch.setenv(name, "system")
    frame = define_frame(preset={f"env.{name}": "preset"})
    try:
        environment = await frame.get("env")
        assert isinstance(environment, BoundEnvironment)
        assert await environment.get(name) == "preset"
        frame.mixin({f"env.{name}": None, "env.PREFIX.value": 42})
        assert await environment.get(name, "fallback") is None
        prefix = await environment.PREFIX
        assert isinstance(prefix, FrameProxy)
        assert await prefix.value == 42
        assert await frame.evaluate("env.PREFIX.value") == 42
        names = await frame.evaluate("env.field_names()")
        assert isinstance(names, list)
        assert name in names
        assert env.get(name) == "system"
    finally:
        await frame.close()
