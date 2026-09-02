"""Behavioural tests for live process-environment access."""

import pytest

import lclang
from lclang.utils import env
from lclang.utils.environment import BoundEnvironment


def test_python_environment_reads_are_live_and_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attribute and get access observe current process state without mutation."""
    name = "LCLANG_ENV_LIVE_TEST"
    invalid = "LCLANG-ENV-INVALID"
    monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(invalid, raising=False)
    assert getattr(env, name) is None
    private_name = "__missing__"
    with pytest.raises(AttributeError):
        getattr(env, private_name)
    assert env.get(name) is None
    assert env.get(invalid, "fallback") == "fallback"
    monkeypatch.setenv(name, "first")
    monkeypatch.setenv(invalid, "second")
    assert getattr(env, name) == "first"
    assert env.get(invalid) == "second"
    monkeypatch.setenv(name, "changed")
    assert getattr(env, name) == "changed"
    with pytest.raises(TypeError):
        env.get(1)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_lcl_environment_falls_back_after_scoped_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frame bindings win without changing live environment fallback values."""
    monkeypatch.setenv("LCLANG_ENV_ALPHA", "system-alpha")
    monkeypatch.setenv("LCLANG_ENV_BETA", "system-beta")
    monkeypatch.delenv("LCLANG_ENV_MISSING", raising=False)
    frame = lclang.define_frame(
        lclang.define_module(
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
        with pytest.raises(AttributeError):
            getattr(environment, private_name)
        with pytest.raises(TypeError):
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
    frame = lclang.define_frame(preset={f"env.{name}": "preset"})
    try:
        environment = await frame.get("env")
        assert isinstance(environment, BoundEnvironment)
        assert await environment.get(name) == "preset"
        frame.mixin({f"env.{name}": None, "env.PREFIX.value": 42})
        assert await environment.get(name, "fallback") is None
        prefix = await environment.PREFIX
        assert isinstance(prefix, lclang.FrameProxy)
        assert await prefix.value == 42
        assert await frame.evaluate("env.PREFIX.value") == 42
        names = await frame.evaluate("env.field_names()")
        assert isinstance(names, list)
        assert name in names
        assert env.get(name) == "system"
    finally:
        await frame.close()
