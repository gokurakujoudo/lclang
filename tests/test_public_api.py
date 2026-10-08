"""Acceptance tests for the stable package-root language API."""

from importlib import import_module

import pytest

import lclang
from lclang.ast import LclConstant
from lclang.lang import parse_expression, to_source


def test_root_exports_language_front_end_services() -> None:
    """Callers can parse and print without importing implementation packages."""
    assert lclang.parse_expression is parse_expression
    assert lclang.to_source is to_source
    node = lclang.parse_expression("1 + 2")
    assert lclang.to_source(node) == "1 + 2"


def test_ast_families_remain_namespaced() -> None:
    """Root exports stay small while AST construction remains available."""
    assert isinstance(lclang.parse_expression("1"), LclConstant)
    assert "parse_expression" in lclang.__all__
    assert "to_source" in lclang.__all__


@pytest.mark.asyncio
async def test_root_exports_record_result_type() -> None:
    """Evaluated records have one stable package-root Python type."""
    module = lclang.define_module("record", {"result": "{answer=42}"})
    async with lclang.define_frame(module) as frame:
        value = await frame.get("result")
        assert isinstance(value, lclang.LclRecord)
        assert value.answer == 42
    assert lclang.__all__.count("LclRecord") == 1


@pytest.mark.parametrize("module_name", ("lclang", "lclang.lang", "lclang.lang.evaluator"))
def test_standalone_evaluation_is_not_a_public_entrypoint(module_name: str) -> None:
    """Supported namespaces guide callers through Modules and Frames."""
    namespace = import_module(module_name)
    for name in ("evaluate", "evaluate_sync"):
        assert name not in namespace.__all__
        assert not hasattr(namespace, name)


@pytest.mark.asyncio
async def test_module_frame_evaluation_shares_builtins_and_scoped_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh Frames resolve standard names and overrides in one closed scope."""
    name = "LCLANG_PUBLIC_API_PORT"
    monkeypatch.setenv(name, "80")
    module = lclang.define_module(
        "settings",
        {"result": f"int(env.{name}) + len(label)", "missing": "unknown"},
    )
    async with lclang.define_frame(module, preset={f"env.{name}": "41", "label": "x"}) as frame:
        assert await frame.get("result") == 42
        with pytest.raises(lclang.LclNameError, match="unknown variable: unknown") as failure:
            await frame.get("missing")
        assert failure.value.variable_stack == ("missing",)
    with pytest.raises(lclang.LclClosedFrameError):
        await frame.get("result")
    async with lclang.define_frame(module, preset={"label": "x"}) as next_frame:
        assert await next_frame.get("result") == 81
