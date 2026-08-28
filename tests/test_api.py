"""Behavioural tests mirroring :mod:`lclang.api`."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

import lclang


@pytest.mark.asyncio
async def test_shortcuts_use_the_complete_default_hierarchy() -> None:
    """Sunny: source definitions see reviewed namespaces and safe builtins."""
    expressions = {
        "result": 'json.encode({"size": len(range(4))})',
    }
    module = lclang.define_module("app", expressions)
    expressions["result"] = "0"
    frame = lclang.define_frame(module)

    assert await frame.get("result") == '{"size":4}'
    assert frame.parent is lclang.LCL_IMPORTS
    assert lclang.LCL_IMPORTS.parent is lclang.LCL_RUNTIME
    assert lclang.LCL_RUNTIME.parent is lclang.LCL_BUILTINS
    assert lclang.LCL_BUILTINS.parent is lclang.LCL_ROOT
    assert lclang.LCL_ROOT.parent is None
    assert lclang.LCL_ROOT.native_values is True
    assert lclang.LCL_BUILTINS.native_values is True
    assert lclang.LCL_RUNTIME.native_values is False
    assert lclang.LCL_IMPORTS.native_values is False
    assert tuple(lclang.LCL_ROOT.values) == ("lhs",)
    assert {"iter", "text", "data", "json", "calendars"} <= set(
        lclang.LCL_BUILTINS.values
    )
    assert lclang.to_source(module.definitions["result"]) != expressions["result"]


@pytest.mark.asyncio
async def test_module_definitions_share_record_attributes_with_python() -> None:
    """Composite record definitions support dependent LCL and Python reads."""
    module = lclang.define_module(
        "profile",
        {
            "profile": "{name=first_name, active=enabled}",
            "label": 'f"{profile.name}:{profile.active}"',
        },
    )
    async with lclang.define_frame(
        module,
        preset={"first_name": "Ada", "enabled": True},
    ) as frame:
        profile = await frame.get("profile")
        assert isinstance(profile, lclang.LclRecord)
        assert profile.name == "Ada"
        assert await frame.get("label") == "Ada:True"


def test_builtin_layer_has_a_fixed_ambient_free_inventory() -> None:
    """The standard layer excludes I/O, dynamic code, import, and mutation."""
    expected = {
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
    assert set(lclang.LCL_BUILTINS.values) == expected
    assert {"open", "input", "eval", "exec", "compile", "__import__"}.isdisjoint(
        lclang.LCL_BUILTINS.values
    )


@pytest.mark.asyncio
async def test_custom_runtime_preset_and_user_module_follow_precedence() -> None:
    """Composite: user, imports, runtime, builtins, and root compose in order."""
    runtime = lclang.Frame(
        lclang.define_module("runtime", {}),
        lclang.FrameId("run:1"),
        values={"cli": SimpleNamespace(scale=3), "shared": 4},
        parent=lclang.LCL_BUILTINS,
    )
    module = lclang.define_module(
        "app",
        {
            "shared": "7",
            "result": ('json.encode({"value": shared + imported + cli.scale + len([0])})'),
        },
    )
    preset: dict[str, object] = {"shared": 5, "imported": 2}
    frame = lclang.define_frame(module, base=runtime, preset=preset)
    preset["imported"] = 100

    assert await frame.get("result") == '{"value":13}'
    assert frame.parent is not None
    assert frame.parent.values == {"shared": 5, "imported": 2}
    assert frame.parent.parent is runtime
    assert runtime.parent is lclang.LCL_BUILTINS


@pytest.mark.asyncio
async def test_empty_module_and_custom_preset_still_make_a_user_frame() -> None:
    """An omitted module retains a usable leaf above a detached import layer."""
    frame = lclang.define_frame(preset={"answer": 42})
    assert await frame.get("answer") == 42
    assert frame.module.definitions == {}
    assert frame.parent is not lclang.LCL_IMPORTS


@pytest.mark.parametrize(
    ("name", "expressions", "error"),
    [
        (1, {}, TypeError),
        ("app", [], TypeError),
        ("app", {1: "1"}, TypeError),
        ("app", {"value": 1}, TypeError),
        ("", {}, ValueError),
    ],
)
def test_define_module_rejects_invalid_inputs(
    name: object,
    expressions: object,
    error: type[Exception],
) -> None:
    """Rainy: shortcut validation fails before publishing a Module."""
    with pytest.raises(error):
        lclang.define_module(name, expressions)  # type: ignore[arg-type]


def test_define_module_preserves_structured_syntax_errors() -> None:
    """Malformed expression source keeps the parser's public error boundary."""
    with pytest.raises(lclang.LclSyntaxError):
        lclang.define_module("app", {"broken": "1 +"})


@pytest.mark.parametrize(
    ("module", "base", "preset"),
    [
        (object(), lclang.LCL_RUNTIME, None),
        (None, object(), None),
        (None, lclang.LCL_RUNTIME, []),
        (None, lclang.LCL_RUNTIME, {"": 1}),
    ],
)
def test_define_frame_rejects_invalid_inputs(
    module: object,
    base: object,
    preset: object,
) -> None:
    """Rainy: invalid hierarchy inputs cannot yield partial Frames."""
    expected = ValueError if preset == {"": 1} else TypeError
    with pytest.raises(expected):
        lclang.define_frame(
            cast(Any, module),
            base=cast(Any, base),
            preset=cast(Any, preset),
        )
