"""Concise construction API and canonical LCL Frame hierarchy.

Defines ``define_module``, ``define_frame``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from lclang.common.binding_mask import normalize_masked_mapping
from lclang.common.identifiers import FrameId, ModuleName
from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.error.verbose_diagnostic import internal_masked_scope
from lclang.lang.ast import LclAstNode
from lclang.lang.common.frame_proxy_marker import FRAME_PROXY, FrameProxyMarker
from lclang.lang.common.override_marker import OverrideMarker
from lclang.lang.engine.evaluator.definition_scope import lhs
from lclang.lang.engine.parser import parse_expression
from lclang.lang.runtime.frame import Frame
from lclang.lang.runtime.module import Module
from lclang.lang.stdlib.builtin_preset import STANDARD_PRESET
from lclang.lang.stdlib.calendar_namespace import CALENDARS_NAMESPACE
from lclang.lang.stdlib.date_conversion import parse_ymd, to_ymd
from lclang.lang.stdlib.recursive_function import recursive
from lclang.utils.calendar.loading import (
    use_calendar_manager,
    use_file_system_hardcoded_calendar_loader,
)
from lclang.utils.process_environment import env
from lclang.utils.snowflake_id import SnowflakeGenerator

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


@guard_failure(LclValidationError, DataModelErrorCode.E44_MODULE_FRAME_CONSTRUCTION_NATIVE_FAILURE)
def define_module(
    name: str,
    exprs: Mapping[str, str | FrameProxyMarker | OverrideMarker],
) -> Module:
    """Parse source expressions into one immutable runtime Module.

    :param name: Non-empty module name.
    :param exprs: Definition names mapped to complete LCL source expressions.
    :returns: Detached Module containing parsed custom AST definitions.
    :raises LclValidationError: If expressions are not a string-keyed dictionary
       of strings or markers.
    :raises LclValidationError: If the module or a definition name is empty.
    :raises LclSyntaxError: If an expression is empty or malformed.

    .. note::
       Expressions are parsed in dictionary insertion order and caller mutation
       cannot change the returned Module.
    """
    if not isinstance(name, str):
        raise LclValidationError(
            "module name must be a string", code=DataModelErrorCode.E44_MODULE_NAME_MUST_BE_A_STRING
        )
    if not isinstance(exprs, dict):
        raise LclValidationError(
            "module expressions must be a dictionary",
            code=DataModelErrorCode.E44_MODULE_EXPRESSIONS_MUST_BE_A_DICTIONARY,
        )
    if any(not isinstance(key, str) for key in exprs):
        raise LclValidationError(
            "module definition names must be strings",
            code=DataModelErrorCode.E44_MODULE_NAME_MUST_BE_A_STRING,
        )
    if any(
        not isinstance(source, (str, OverrideMarker)) and source is not FRAME_PROXY
        for source in exprs.values()
    ):
        raise LclValidationError(
            "module expressions must be strings or declaration markers",
            code=DataModelErrorCode.E44_MODULE_NAME_MUST_BE_A_STRING,
        )
    normalized, masked_names = normalize_masked_mapping(exprs)
    definitions: dict[str, LclAstNode] = {}
    for key, source in normalized.items():
        with internal_masked_scope(key in masked_names):
            definitions[key] = parse_expression(
                "FRAME_PROXY"
                if source is FRAME_PROXY
                else source.value if isinstance(source, OverrideMarker) else cast(str, source)
            )
    return Module(ModuleName(name), definitions, masked_names=masked_names)


@guard_failure(LclValidationError, DataModelErrorCode.E44_MODULE_FRAME_CONSTRUCTION_NATIVE_FAILURE)
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
    :raises LclValidationError: If *module*, *base*, or *preset* has the wrong type.
    :raises LclValidationError: If a preset binding name is empty.

    .. note::
       With the default base and no preset, the immutable empty `LCL_IMPORTS`
       ancestor is reused; every user Frame still owns independent runtime state.
       Prefer ``async with define_frame(...) as frame:`` so scope exit closes
       that owned state deterministically.
    """
    if module is not None and not isinstance(module, Module):
        raise LclValidationError(
            "frame module must be a Module",
            code=DataModelErrorCode.E44_FRAME_MODULE_MUST_BE_A_MODULE,
        )
    if not isinstance(base, Frame):
        raise LclValidationError(
            "frame base must be a Frame", code=DataModelErrorCode.E44_FRAME_BASE_MUST_BE_A_FRAME
        )
    if preset is not None and not isinstance(preset, dict):
        raise LclValidationError(
            "frame preset must be a dictionary",
            code=DataModelErrorCode.E44_MODULE_EXPRESSIONS_MUST_BE_A_DICTIONARY,
        )
    selected_module = LCL_USER_MODULE if module is None else module
    if base is LCL_RUNTIME and preset is None:
        imports = LCL_IMPORTS
    else:
        imports = base.derive(
            LCL_IMPORTS_MODULE,
            {} if preset is None else preset,
        )
    return imports.derive(selected_module)
