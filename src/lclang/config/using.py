"""Position-sensitive evaluation for dynamic configuration targets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from lclang.ast import LclAstNode
from lclang.config.errors import LclConfigUsingError
from lclang.config.model import ConfigDefinition, ConfigUsing
from lclang.masking import normalize_masked_mapping
from lclang.runtime import Module
from lclang.types import ModuleName

# Transient module name for definitions visible before one using declaration.
# Unitless private evaluation labels below distinguish dynamic-using context, overrides and
# targets in diagnostic Frames. Fixed labels come from the loader implementation and avoid
# collisions with ordinary configuration names.
USING_CONTEXT_MODULE = ModuleName("using_context")
# Transient module name for call-level using overrides.
USING_OVERRIDES_MODULE = ModuleName("using_overrides")
# Transient binding name holding the dynamic target expression.
USING_TARGET_NAME = "using_target"
# Transient module name for the dynamic target expression.
USING_TARGET_MODULE = ModuleName("using_target")


def snapshot_using_overrides(
    overrides: Mapping[str, object] | None,
) -> dict[str, object]:
    """Detach one optional public using-override mapping.

    :param overrides: Literal values and semantic LCL expressions.
    :returns: Fresh string-keyed override dictionary.
    :raises TypeError: If the mapping or one key has an unsupported type.
    """
    if overrides is None:
        return {}
    if not isinstance(overrides, Mapping):
        raise TypeError("config using overrides must be a mapping")
    snapshot = dict(overrides)
    if any(not isinstance(name, str) for name in snapshot):
        raise TypeError("config using override names must be strings")
    return snapshot


async def evaluate_using_target(
    declaration: ConfigUsing,
    preceding: Sequence[ConfigDefinition],
    overrides: Mapping[str, object],
) -> str:
    """Evaluate one dynamic target against its chronological context.

    :param declaration: Dynamic using declaration to resolve.
    :param preceding: Expanded definitions occurring before the declaration.
    :param overrides: Detached call-level values or semantic expressions.
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
        )
    except Exception as error:
        raise LclConfigUsingError(
            f"cannot evaluate using target: {error}",
            span=declaration.span,
        ) from error
    if not isinstance(result, str) or not result:
        raise LclConfigUsingError(
            "using target must evaluate to non-empty text",
            span=declaration.span,
        )
    if Path(result).suffix != ".lclcfg":
        raise LclConfigUsingError(
            "using target must end in .lclcfg",
            span=declaration.span,
        )
    return result


async def evaluate_target_expression(
    expression: LclAstNode,
    preceding: Sequence[ConfigDefinition],
    overrides: Mapping[str, object],
) -> object:
    """Run one target expression in disposable Frame layers.

    :param expression: Parsed semantic f-string expression.
    :param preceding: Expanded chronological definitions.
    :param overrides: Detached call-level override mapping.
    :returns: Fully evaluated target value.
    """
    from lclang.api import LCL_IMPORTS

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
    context = LCL_IMPORTS.derive(
        Module(USING_CONTEXT_MODULE, winners, masked_names=frozenset(masks))
    )
    async with context:
        override_frame = context.derive(
            Module(
                USING_OVERRIDES_MODULE,
                override_definitions,
                masked_names=(override_masks | masks) & override_definitions.keys(),
            ),
            override_values,
            masked_names=override_masks | (masks & override_values.keys()),
        )
        async with override_frame:
            target = override_frame.derive(
                Module(USING_TARGET_MODULE, {USING_TARGET_NAME: expression})
            )
            async with target:
                return await target.get(USING_TARGET_NAME)
