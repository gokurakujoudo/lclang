"""Semantic formatted-string evaluation and conversion."""

from __future__ import annotations

from typing import cast

from pylcl.ast import LclFormattedValue, LclJoinedString, LclStringText
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver
from pylcl.lang.printer import to_source


async def _evaluate_joined(
    node: LclJoinedString,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> str:
    """Evaluate text and replacement fields in source order.

    :param node: Joined-string AST node containing literal and formatted parts.
    :param resolver: Resolver supplying names referenced by replacement fields.
    :param evaluate: Recursive evaluator for field expressions and format specs.
    :returns: Rendered formatted-string value.

    .. note::
       Literal text is preserved exactly while each formatted field is
       rendered through :func:`_format_value`.
    """
    parts: list[str] = []
    for part in node.values:
        if isinstance(part, LclStringText):
            parts.append(part.text)
        else:
            parts.append(await _format_value(cast(LclFormattedValue, part), resolver, evaluate))
    return "".join(parts)


async def _format_value(
    field: LclFormattedValue,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> str:
    """Evaluate and format one replacement field.

    :param field: Formatted-value AST node to render.
    :param resolver: Resolver supplying names referenced by the field.
    :param evaluate: Recursive evaluator for the field expression and its
       optional format specification.
    :returns: Converted, optionally formatted field text.

    .. note::
       Debug fields expose canonical expression source, and a bare debug field
       defaults to ``repr`` conversion before applying any format specification.
    """
    value = await evaluate(field.expression, resolver)
    conversion = field.conversion
    if conversion is None and field.debug and field.format_spec is None:
        conversion = "r"
    if conversion == "s":
        value = str(value)
    elif conversion == "r":
        value = repr(value)
    elif conversion == "a":
        value = ascii(value)
    prefix = f"{to_source(field.expression)}=" if field.debug else ""
    if field.format_spec is None:
        return prefix + str(value)
    spec = cast(str, await evaluate(field.format_spec, resolver))
    return prefix + format(value, spec)
