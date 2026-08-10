"""Evaluation for tuple, list, set, and dictionary displays."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pylcl.ast import (
    LclAstNode,
    LclDict,
    LclDictUnpack,
    LclKeyValue,
    LclList,
    LclSet,
    LclStarred,
    LclTuple,
)
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver
from pylcl.lang.evaluator.iteration import iterate_values

type DisplayNode = LclTuple | LclList | LclSet | LclDict


async def _evaluate_display(
    node: DisplayNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a tuple, list, set, or dictionary display.

    :param node: Collection-display AST node to evaluate.
    :param resolver: Resolver providing values for nested expressions.
    :param evaluate: Recursive evaluator for display elements and entries.
    :returns: Materialized tuple, list, set, or dictionary value.

    .. note::
       Starred sequence elements and dictionary unpacking are expanded during
       the same left-to-right traversal used for ordinary elements.
    """
    if isinstance(node, LclTuple):
        return tuple(await _sequence(node.elements, resolver, evaluate))
    if isinstance(node, LclList):
        return await _sequence(node.elements, resolver, evaluate)
    if isinstance(node, LclSet):
        return set(await _sequence(node.elements, resolver, evaluate))
    return await _dictionary(node, resolver, evaluate)


async def _sequence(
    elements: tuple[LclAstNode, ...],
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> list[object]:
    """Evaluate sequence elements and flatten starred values.

    :param elements: Ordered tuple, list, or set element expressions.
    :param resolver: Resolver providing values for each element expression.
    :param evaluate: Recursive evaluator for ordinary and starred elements.
    :returns: Evaluated elements in source order before their final container
       type is selected.

    .. note::
       Starred values may come from either sync or async iterables and are
       consumed immediately while the display is being materialized.
    """
    values: list[object] = []
    for element in elements:
        if isinstance(element, LclStarred):
            expanded = await evaluate(element.value, resolver)
            values.extend([item async for item in iterate_values(expanded)])
        else:
            values.append(await evaluate(element, resolver))
    return values


async def _dictionary(
    node: LclDict,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> dict[object, object]:
    """Evaluate dictionary entries and merge unpacked mappings.

    :param node: Dictionary-display AST node containing key-value entries.
    :param resolver: Resolver providing values for keys, values, and unpacking.
    :param evaluate: Recursive evaluator for dictionary entry expressions.
    :returns: Materialized dictionary assembled in source order.
    :raises TypeError: If an entry has an unsupported AST type or a
       dictionary-unpacking value is not a mapping.

    .. note::
       Later entries replace earlier values for duplicate keys, matching normal
       dictionary update semantics.
    """
    result: dict[object, object] = {}
    for entry in node.entries:
        if isinstance(entry, LclKeyValue):
            key = await evaluate(entry.key, resolver)
            result[key] = await evaluate(entry.value, resolver)
        elif isinstance(entry, LclDictUnpack):
            value = await evaluate(entry.value, resolver)
            if not isinstance(value, Mapping):
                raise TypeError("dictionary unpacking requires a mapping")
            result.update(cast(Mapping[object, object], value))
        else:
            raise TypeError("unsupported dictionary display entry")
    return result
