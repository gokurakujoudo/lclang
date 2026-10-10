"""Position-sensitive evaluation for dynamic configuration targets.

Defines ``snapshot_using_overrides``, ``evaluate_using_target``,
``evaluate_target_expression``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from lclang.common.binding_mask import normalize_masked_mapping
from lclang.common.identifiers import ModuleName
from lclang.config.config_document import ConfigDefinition, ConfigImport, ConfigUsing
from lclang.error import ConfigurationErrorCode, LclConfigError, LclError
from lclang.error.configuration_exception import LclConfigUsingError
from lclang.error.exception_base import LclValidationError
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_async_failure, guard_failure

# Transient module name for definitions visible before one using declaration.
# Unitless private evaluation labels below distinguish dynamic-using context, overrides and
# targets in diagnostic Frames. Fixed labels come from the loader implementation and avoid
# collisions with ordinary configuration names.
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.evaluator.evaluation_journal import ACTIVE_TARGET_EXPRESSION
from lclang.lang.runtime import Module

# Unitless module label identifies chronological definitions used to evaluate a file target.
USING_CONTEXT_MODULE = ModuleName("using_context")
# Transient module name for call-level using overrides.
USING_OVERRIDES_MODULE = ModuleName("using_overrides")
# Unitless transient target binding uses the configuration-reserved __ prefix
# so an ordinary user definition cannot be shadowed during target selection.
USING_TARGET_NAME = "__lclang_file_target"
# Transient module name for the dynamic target expression.
USING_TARGET_MODULE = ModuleName("using_target")


@guard_failure(LclConfigError, ConfigurationErrorCode.E24_CONFIG_TARGET_EVALUATION_NATIVE_FAILURE)
def snapshot_using_overrides(
    overrides: Mapping[str, object] | None,
) -> dict[str, object]:
    """Detach one optional public using-override mapping.

    :param overrides: Literal values and semantic LCL expressions.
    :returns: Fresh string-keyed override dictionary.
    :raises LclValidationError: If the mapping or one key has an unsupported type.
    """
    if overrides is None:
        return {}
    if not isinstance(overrides, Mapping):
        raise LclValidationError(
            "config using overrides must be a mapping",
            code=ConfigurationErrorCode.E24_CONFIG_USING_OVERRIDES_MUST_BE_A_MAPPING,
        )
    snapshot = dict(overrides)
    if any(not isinstance(name, str) for name in snapshot):
        raise LclValidationError(
            "config using override names must be strings",
            code=ConfigurationErrorCode.E24_CONFIG_USING_OVERRIDE_NAMES_MUST_BE_STRINGS,
        )
    return snapshot


@guard_async_failure(
    LclConfigError, ConfigurationErrorCode.E24_CONFIG_TARGET_EVALUATION_NATIVE_FAILURE
)
async def evaluate_using_target(
    declaration: ConfigUsing | ConfigImport,
    preceding: Sequence[ConfigDefinition],
    overrides: Mapping[str, object],
    *,
    namespace_names: frozenset[str] = frozenset(),
) -> str:
    """Evaluate one dynamic target against its chronological context.

    :param declaration: Dynamic using declaration to resolve.
    :param preceding: Expanded definitions occurring before the declaration.
    :param overrides: Detached call-level values or semantic expressions.
    :param namespace_names: Explicit namespaces visible before this declaration.
    :returns: Non-empty path text ending in ``.lclcfg``.
    :raises LclConfigUsingError: If construction or evaluation fails.
    """
    if isinstance(declaration.target, str):
        return declaration.target
    try:
        result = await evaluate_target_expression(
            declaration.target,
            preceding,
            overrides,
            namespace_names=namespace_names,
        )
    except Exception as error:
        if isinstance(error, ExceptionGroup):
            failure = wrap_failure(
                cast(ExceptionGroup[Exception], error),
                LclConfigUsingError,
                (
                    error.code
                    if isinstance(error, LclError)
                    else ConfigurationErrorCode.E24_CANNOT_EVALUATE_FILE_TARGET
                ),
                span=declaration.span,
            )
            failure.add_note("configuration file target")
            raise failure from failure.__cause__
        raise LclConfigUsingError(
            "cannot evaluate file target",
            span=declaration.span,
            code=(
                error.code
                if isinstance(error, LclError)
                else ConfigurationErrorCode.E24_CANNOT_EVALUATE_FILE_TARGET
            ),
        ) from error
    if not isinstance(result, str) or not result:
        raise LclConfigUsingError(
            "using target must evaluate to non-empty text",
            span=declaration.span,
            code=ConfigurationErrorCode.E24_USING_TARGET_MUST_EVALUATE_TO_NON_EMPTY_TEXT,
        )
    if Path(result).suffix != ".lclcfg":
        raise LclConfigUsingError(
            "using target must end in .lclcfg",
            span=declaration.span,
            code=ConfigurationErrorCode.E24_USING_TARGET_MUST_END_IN_LCLCFG,
        )
    return result


@guard_async_failure(
    LclConfigError, ConfigurationErrorCode.E24_CONFIG_TARGET_EVALUATION_NATIVE_FAILURE
)
async def evaluate_target_expression(
    expression: LclAstNode,
    preceding: Sequence[ConfigDefinition],
    overrides: Mapping[str, object],
    *,
    namespace_names: frozenset[str] = frozenset(),
) -> object:
    """Run one target expression in disposable Frame layers.

    :param expression: Parsed semantic f-string expression.
    :param preceding: Expanded chronological definitions.
    :param overrides: Detached call-level override mapping.
    :param namespace_names: Explicit namespaces in the chronological context.
    :returns: Fully evaluated target value.
    """
    from lclang.lang.runtime.module_frame_factory import LCL_IMPORTS

    winners: dict[str, LclAstNode] = {}
    masks: set[str] = set()
    for definition in preceding:
        name = str(definition.name)
        winners[name] = definition.expression
        if definition.masked:
            masks.add(name)
    normalized, override_masks = normalize_masked_mapping(overrides)
    override_definitions = {
        name: value for name, value in normalized.items() if isinstance(value, LclAstNode)
    }
    override_values = {
        name: value for name, value in normalized.items() if not isinstance(value, LclAstNode)
    }
    definitions = {**winners, **override_definitions}
    definitions = {name: node for name, node in definitions.items() if name not in override_values}
    all_masks = frozenset(masks) | override_masks
    context = LCL_IMPORTS.derive(
        Module(
            USING_CONTEXT_MODULE,
            definitions,
            masked_names=all_masks & definitions.keys(),
            namespace_names=namespace_names,
        ),
        override_values,
        masked_names=all_masks,
    )
    async with context:
        target = context.derive(Module(USING_TARGET_MODULE, {USING_TARGET_NAME: expression}))
        async with target:
            token = ACTIVE_TARGET_EXPRESSION.set(expression)
            try:
                return await target.get(USING_TARGET_NAME)
            finally:
                ACTIVE_TARGET_EXPRESSION.reset(token)
