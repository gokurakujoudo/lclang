"""Concise construction API and canonical LCL Frame hierarchy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from lclang.ast import LclAstNode
from lclang.diagnostics import internal_masked_scope
from lclang.lang.evaluator.definition_context import lhs
from lclang.lang.parser import parse_expression
from lclang.masking import normalize_masked_mapping
from lclang.runtime.frame import Frame
from lclang.runtime.modules import Module
from lclang.scopes import FRAME_PROXY, FrameProxyMarker
from lclang.stdlib.builtins import STANDARD_PRESET
from lclang.stdlib.dates import parse_ymd, to_ymd
from lclang.stdlib.recursion import recursive
from lclang.types import FrameId, ModuleName
from lclang.utils.calendar.lcl import CALENDARS_NAMESPACE
from lclang.utils.calendar.loading import (
    use_calendar_manager,
    use_file_system_hardcoded_calendar_loader,
)
from lclang.utils.environment import env
from lclang.utils.snowflake import SnowflakeGenerator

# Curated ordinary Python values and explicit environment/calendar utilities.
# Unitless canonical names and objects below come from the runtime hierarchy contract. Stable
# IDs distinguish root, builtins, runtime, imports and user layers; shared defaults preserve
# their precedence. The builtin inventory includes explicit environment and calendar-loader
# capabilities, plus explicitly constructed clock-backed Snowflake generators.
LCL_BUILTIN_VALUES: dict[str, object] = {
    **STANDARD_PRESET.values,
    "SnowflakeGenerator": SnowflakeGenerator,
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "bytes": bytes,
    "chr": chr,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "env": env,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "oct": oct,
    "ord": ord,
    "parse_ymd": parse_ymd,
    "pow": pow,
    "range": range,
    "recursive": recursive,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "to_ymd": to_ymd,
    "calendars": CALENDARS_NAMESPACE,
    "use_calendar_manager": use_calendar_manager,
    "use_file_system_hardcoded_calendar_loader": (use_file_system_hardcoded_calendar_loader),
    "zip": zip,
}

# Empty immutable module identifying the root LCL mixin layer.
LCL_ROOT_MODULE = Module(ModuleName("LCL_ROOT"), {})
# Empty immutable module identifying the standard builtin layer.
LCL_BUILTINS_MODULE = Module(ModuleName("LCL_BUILTINS"), {})
# Empty immutable module identifying a default or per-invocation runtime layer.
LCL_RUNTIME_MODULE = Module(ModuleName("LCL_RUNTIME"), {})
# Empty immutable module identifying a detached imports/preset layer.
LCL_IMPORTS_MODULE = Module(ModuleName("LCL_IMPORTS"), {})
# Empty immutable module used when a shortcut caller omits user definitions.
LCL_USER_MODULE = Module(ModuleName("user"), {})

# Root LCL mixin providing the reviewed standard namespaces.
LCL_ROOT = Frame(
    LCL_ROOT_MODULE,
    FrameId("LCL_ROOT"),
    values={"lhs": lhs},
    native_values=True,
)
# Standard Python values and explicit utilities above the LCL mixin.
LCL_BUILTINS = Frame(
    LCL_BUILTINS_MODULE,
    FrameId("LCL_BUILTINS"),
    values=LCL_BUILTIN_VALUES,
    parent=LCL_ROOT,
    native_values=True,
)
# Empty default run layer, replaceable with one CLI-aware Frame per invocation.
LCL_RUNTIME = Frame(
    LCL_RUNTIME_MODULE,
    FrameId("LCL_RUNTIME"),
    parent=LCL_BUILTINS,
)
# Empty default preset layer reused by shortcut Frames without custom imports.
LCL_IMPORTS = Frame(
    LCL_IMPORTS_MODULE,
    FrameId("LCL_IMPORTS"),
    parent=LCL_RUNTIME,
)


def define_module(
    name: str,
    exprs: Mapping[str, str | FrameProxyMarker],
) -> Module:
    """Parse source expressions into one immutable runtime Module.

    :param name: Non-empty module name.
    :param exprs: Definition names mapped to complete LCL source expressions.
    :returns: Detached Module containing parsed custom AST definitions.
    :raises TypeError: If an input is not a string-keyed dictionary of strings.
    :raises ValueError: If the module or a definition name is empty.
    :raises LclSyntaxError: If an expression is empty or malformed.

    .. note::
       Expressions are parsed in dictionary insertion order and caller mutation
       cannot change the returned Module.
    """
    if not isinstance(name, str):
        raise TypeError("module name must be a string")
    if not isinstance(exprs, dict):
        raise TypeError("module expressions must be a dictionary")
    if any(not isinstance(key, str) for key in exprs):
        raise TypeError("module definition names must be strings")
    if any(not isinstance(source, str) and source is not FRAME_PROXY for source in exprs.values()):
        raise TypeError("module expressions must be strings or FRAME_PROXY")
    normalized, masked_names = normalize_masked_mapping(exprs)
    definitions: dict[str, LclAstNode] = {}
    for key, source in normalized.items():
        with internal_masked_scope(key in masked_names):
            definitions[key] = parse_expression(
                "FRAME_PROXY" if source is FRAME_PROXY else cast(str, source)
            )
    return Module(ModuleName(name), definitions, masked_names=masked_names)


def define_frame(
    module: Module | None = None,
    base: Frame = LCL_RUNTIME,
    preset: dict[str, object] | None = None,
) -> Frame:
    """Create a fresh user Frame above runtime and preset layers.

    :param module: Optional user definitions, or an empty module when omitted.
    :param base: Borrowed per-run base Frame below the imports layer.
    :param preset: Optional host imports copied into a fresh imports layer.
    :returns: Fresh user Frame with independent cache and lifecycle state.
    :raises TypeError: If *module*, *base*, or *preset* has the wrong type.
    :raises ValueError: If a preset binding name is empty.

    .. note::
       With the default base and no preset, the immutable empty `LCL_IMPORTS`
       ancestor is reused; every user Frame still owns independent runtime state.
       Prefer ``async with define_frame(...) as frame:`` so scope exit closes
       that owned state deterministically.
    """
    if module is not None and not isinstance(module, Module):
        raise TypeError("frame module must be a Module")
    if not isinstance(base, Frame):
        raise TypeError("frame base must be a Frame")
    if preset is not None and not isinstance(preset, dict):
        raise TypeError("frame preset must be a dictionary")
    selected_module = LCL_USER_MODULE if module is None else module
    if base is LCL_RUNTIME and preset is None:
        imports = LCL_IMPORTS
    else:
        imports = base.derive(
            LCL_IMPORTS_MODULE,
            {} if preset is None else preset,
        )
    return imports.derive(selected_module)
