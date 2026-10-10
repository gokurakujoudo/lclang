"""Acceptance tests for the stable language API."""

from importlib import import_module

import pytest

import lclang.lang as language
from lclang.error import LclClosedFrameError, LclNameError
from lclang.lang import LclRecord, define_frame, define_module, parse_expression, to_source
from lclang.lang.ast import LclConstant


def test_language_exports_language_front_end_services() -> None:
    """Callers can parse and print without importing implementation packages."""
    assert language.parse_expression is parse_expression
    assert language.to_source is to_source
    node = parse_expression("1 + 2")
    assert to_source(node) == "1 + 2"


def test_ast_families_remain_namespaced() -> None:
    """Language exports stay focused while AST construction remains available."""
    assert isinstance(parse_expression("1"), LclConstant)
    assert "parse_expression" in language.__all__
    assert "to_source" in language.__all__


@pytest.mark.asyncio
async def test_language_exports_record_result_type() -> None:
    """Evaluated records have one stable language Python type."""
    module = define_module("record", {"result": "{answer=42}"})
    async with define_frame(module) as frame:
        value = await frame.get("result")
        assert isinstance(value, LclRecord)
        assert value.answer == 42
    assert language.__all__.count("LclRecord") == 1


@pytest.mark.parametrize("module_name", ("lclang", "lclang.lang", "lclang.lang.engine.evaluator"))
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
    module = define_module(
        "settings",
        {"result": f"int(env.{name}) + len(label)", "missing": "unknown"},
    )
    async with define_frame(module, preset={f"env.{name}": "41", "label": "x"}) as frame:
        assert await frame.get("result") == 42
        with pytest.raises(LclNameError, match="unknown variable: unknown") as failure:
            await frame.get("missing")
        assert failure.value.variable_stack == ("missing",)
    with pytest.raises(LclClosedFrameError):
        await frame.get("result")
    async with define_frame(module, preset={"label": "x"}) as next_frame:
        assert await next_frame.get("result") == 81
