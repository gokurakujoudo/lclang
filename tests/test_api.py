"""Behavioural tests mirroring :mod:`lclang.lang.runtime.module_frame_factory`."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from lclang.error import LclSyntaxError, LclValidationError
from lclang.lang import (
    LCL_BUILTINS,
    LCL_IMPORTS,
    LCL_ROOT,
    LCL_RUNTIME,
    Frame,
    FrameId,
    LclRecord,
    define_frame,
    define_module,
    to_source,
)


@pytest.mark.asyncio
async def test_shortcuts_use_the_complete_default_hierarchy() -> None:
    """Sunny: source definitions see reviewed namespaces and safe builtins."""
    expressions = {
        "result": 'json.encode({"size": len(range(4))})',
    }
    module = define_module("app", expressions)
    expressions["result"] = "0"
    frame = define_frame(module)

    assert await frame.get("result") == '{"size":4}'
    assert frame.parent is LCL_IMPORTS
    assert LCL_IMPORTS.parent is LCL_RUNTIME
    assert LCL_RUNTIME.parent is LCL_BUILTINS
    assert LCL_BUILTINS.parent is LCL_ROOT
    assert LCL_ROOT.parent is None
    assert LCL_ROOT.native_values is True
    assert LCL_BUILTINS.native_values is True
    assert LCL_RUNTIME.native_values is False
    assert LCL_IMPORTS.native_values is False
    assert tuple(LCL_ROOT.values) == ("lhs",)
    assert {"iter", "text", "data", "json", "calendars"} <= set(LCL_BUILTINS.values)
    assert to_source(module.definitions["result"]) != expressions["result"]


@pytest.mark.asyncio
async def test_module_definitions_share_record_attributes_with_python() -> None:
    """Composite record definitions support dependent LCL and Python reads."""
    module = define_module(
        "profile",
        {
            "profile": "{name=first_name, active=enabled}",
            "label": 'f"{profile.name}:{profile.active}"',
        },
    )
    async with define_frame(
        module,
        preset={"first_name": "Ada", "enabled": True},
    ) as frame:
        profile = await frame.get("profile")
        assert isinstance(profile, LclRecord)
        assert profile.name == "Ada"
        assert await frame.get("label") == "Ada:True"


def test_builtin_layer_has_a_fixed_reviewed_inventory() -> None:
    """The standard layer exposes only reviewed utilities and pure operations."""
    expected = {
        "SnowflakeGenerator",
        "abs",
        "all",
        "any",
        "bin",
        "bool",
        "bytes",
        "chr",
        "dict",
        "divmod",
        "enumerate",
        "env",
        "filter",
        "float",
        "format",
        "frozenset",
        "hex",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "oct",
        "ord",
        "pow",
        "parse_ymd",
        "range",
        "recursive",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "to_ymd",
        "iter",
        "text",
        "data",
        "json",
        "calendars",
        "use_calendar_manager",
        "use_file_system_hardcoded_calendar_loader",
        "zip",
    }
    assert set(LCL_BUILTINS.values) == expected
    assert {"open", "input", "eval", "exec", "compile", "__import__"}.isdisjoint(
        LCL_BUILTINS.values
    )


@pytest.mark.asyncio
async def test_custom_runtime_preset_and_user_module_follow_precedence() -> None:
    """Composite: user, imports, runtime, builtins, and root compose in order."""
    runtime = Frame(
        define_module("runtime", {}),
        FrameId("run:1"),
        values={"cli": SimpleNamespace(scale=3), "shared": 4},
        parent=LCL_BUILTINS,
    )
    module = define_module(
        "app",
        {
            "shared": "7",
            "result": ('json.encode({"value": shared + imported + cli.scale + len([0])})'),
        },
    )
    preset: dict[str, object] = {"shared": 5, "imported": 2}
    frame = define_frame(module, base=runtime, preset=preset)
    preset["imported"] = 100

    assert await frame.get("result") == '{"value":13}'
    assert frame.parent is not None
    assert frame.parent.values == {"shared": 5, "imported": 2}
    assert frame.parent.parent is runtime
    assert runtime.parent is LCL_BUILTINS


@pytest.mark.asyncio
async def test_empty_module_and_custom_preset_still_make_a_user_frame() -> None:
    """An omitted module retains a usable leaf above a detached import layer."""
    frame = define_frame(preset={"answer": 42})
    assert await frame.get("answer") == 42
    assert frame.module.definitions == {}
    assert frame.parent is not LCL_IMPORTS


@pytest.mark.parametrize(
    ("name", "expressions", "error"),
    [
        (1, {}, LclValidationError),
        ("app", [], LclValidationError),
        ("app", {1: "1"}, LclValidationError),
        ("app", {"value": 1}, LclValidationError),
        ("", {}, LclValidationError),
    ],
)
def test_define_module_rejects_invalid_inputs(
    name: object,
    expressions: object,
    error: type[Exception],
) -> None:
    """Rainy: shortcut validation fails before publishing a Module."""
    with pytest.raises(error):
        define_module(name, expressions)  # type: ignore[arg-type]


def test_define_module_preserves_structured_syntax_errors() -> None:
    """Malformed expression source keeps the parser's public error boundary."""
    with pytest.raises(LclSyntaxError):
        define_module("app", {"broken": "1 +"})


@pytest.mark.parametrize(
    ("module", "base", "preset"),
    [
        (object(), LCL_RUNTIME, None),
        (None, object(), None),
        (None, LCL_RUNTIME, []),
        (None, LCL_RUNTIME, {"": 1}),
    ],
)
def test_define_frame_rejects_invalid_inputs(
    module: object,
    base: object,
    preset: object,
) -> None:
    """Rainy: invalid hierarchy inputs cannot yield partial Frames."""
    expected = LclValidationError
    with pytest.raises(expected):
        define_frame(
            cast(Any, module),
            base=cast(Any, base),
            preset=cast(Any, preset),
        )
