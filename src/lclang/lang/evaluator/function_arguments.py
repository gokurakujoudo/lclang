"""LCL function default resolution and call-argument binding."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast import LclParameter, ParameterKind
from lclang.lang.evaluator._types import EvaluateNode
from lclang.lang.evaluator.context import Resolver

# Sentinel distinguishing a missing parameter default from an explicit value.
MISSING_PARAMETER = object()


@dataclass(frozen=True, slots=True)
class BoundParameter:
    """Store one normalized parameter binding rule.

    :param name: String name exposed to the function body.
    :param kind: Positional, variadic, or keyword parameter category.
    :param default: Pre-evaluated default value, or the missing sentinel.

    .. note::
       Immutable rules let one closure bind calls concurrently.
    """

    name: str
    kind: ParameterKind
    default: object = MISSING_PARAMETER


async def resolve_default(
    parameter: LclParameter,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Resolve one parameter default or return the missing sentinel.

    :param parameter: Parameter whose optional default should be evaluated.
    :param resolver: Resolver used by the default expression.
    :param evaluate: Recursive evaluator for the default expression.
    :returns: Evaluated default value, or the sentinel when absent.

    .. note::
       Defaults are evaluated once when the function value is created.
    """
    if parameter.default is None:
        return MISSING_PARAMETER
    return await evaluate(parameter.default, resolver)


def bind_arguments(
    parameters: tuple[BoundParameter, ...],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> dict[str, object]:
    """Bind positional, variadic, keyword-only, and named arguments.

    :param parameters: Ordered normalized parameter rules.
    :param args: Positional call arguments.
    :param kwargs: Named call arguments.
    :returns: Local name-to-value bindings for one invocation.
    :raises TypeError: If arguments are duplicated, missing, or unexpected.

    .. note::
       Named arguments are copied, so caller-owned input is never mutated.
    """
    values: dict[str, object] = {}
    named = dict(kwargs)
    position = 0
    variadic_position = False
    variadic_keyword = False
    for parameter in parameters:
        if parameter.kind is ParameterKind.POSITIONAL:
            position = bind_positional(parameter, args, position, named, values)
        elif parameter.kind is ParameterKind.VAR_POSITIONAL:
            values[parameter.name] = args[position:]
            position = len(args)
            variadic_position = True
        elif parameter.kind is ParameterKind.KEYWORD_ONLY:
            values[parameter.name] = take_named(parameter, named)
        else:
            values[parameter.name] = dict(named)
            named.clear()
            variadic_keyword = True
    if position < len(args) and not variadic_position:
        raise TypeError("too many positional arguments")
    if named and not variadic_keyword:
        unexpected = next(iter(named))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    return values


def bind_positional(
    parameter: BoundParameter,
    args: tuple[object, ...],
    position: int,
    named: dict[str, object],
    values: dict[str, object],
) -> int:
    """Bind one ordinary positional parameter and advance the cursor.

    :param parameter: Positional parameter rule to satisfy.
    :param args: Positional call arguments.
    :param position: Current zero-based positional cursor.
    :param named: Remaining named arguments.
    :param values: Binding map populated for the invocation.
    :returns: Cursor after positional, named, or default binding.
    :raises TypeError: If a value is duplicated or absent.

    .. note::
       Exhausted positional input falls through to named/default rules.
    """
    if position < len(args):
        if parameter.name in named:
            raise TypeError(f"multiple values for argument: {parameter.name}")
        values[parameter.name] = args[position]
        return position + 1
    values[parameter.name] = take_named(parameter, named)
    return position


def take_named(parameter: BoundParameter, named: dict[str, object]) -> object:
    """Consume a named argument or provide its default value.

    :param parameter: Parameter whose name and default are consulted.
    :param named: Mutable remaining named-argument mapping.
    :returns: Popped argument value or the parameter default.
    :raises TypeError: If a required parameter has no supplied value.

    .. note::
       Popping successful input exposes unexpected names after binding.
    """
    if parameter.name in named:
        return named.pop(parameter.name)
    if parameter.default is not MISSING_PARAMETER:
        return parameter.default
    raise TypeError(f"missing required argument: {parameter.name}")
