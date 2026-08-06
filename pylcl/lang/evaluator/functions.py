"""Function creation, argument binding, closures, and recursion control."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from pylcl.ast import LclAstNode, LclFunction, LclParameter, ParameterKind
from pylcl.errors import LclEvaluationError
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver, ScopedResolver
from pylcl.source import SourceSpan

_MISSING = object()
_ACTIVE_FUNCTIONS: ContextVar[frozenset[int]] = ContextVar(
    "pylcl_active_functions",
    default=frozenset(),
)


@dataclass(frozen=True, slots=True)
class _BoundParameter:
    """Store one normalized parameter binding rule.

    :param name: String name exposed to the function body.
    :param kind: Positional, variadic, or keyword parameter category.
    :param default: Pre-evaluated default value, or the internal missing sentinel.
    .. note:: Instances are immutable so one function closure can bind concurrently.
    """

    name: str
    kind: ParameterKind
    default: object = _MISSING


@dataclass(frozen=True, slots=True)
class LclFunctionValue:
    """Represent one callable LCL closure.

    :param parameters: Parameters with defaults resolved at creation time.
    :param body: Semantic AST expression evaluated on every call.
    :param closure: Defining resolver used beneath invocation locals.
    :param span: Function source range used for recursion diagnostics.

    .. note::
       Calls are async, task-safe, and deliberately non-recursive in LCL V1.
    """

    parameters: tuple[_BoundParameter, ...]
    body: LclAstNode
    closure: Resolver
    span: SourceSpan
    _evaluate: EvaluateNode

    async def __call__(self, *args: object, **kwargs: object) -> object:
        """Bind arguments and evaluate the body in the lexical closure.

        :param args: Positional application values.
        :param kwargs: Named application values.
        :returns: Fully evaluated function body result.
        :raises TypeError: If arguments do not satisfy the parameter contract.
        :raises LclEvaluationError: If this value re-enters in the same task.

        .. note::
           Concurrent calls in distinct tasks have independent recursion state.
        """
        key = id(self)
        active = _ACTIVE_FUNCTIONS.get()
        if key in active:
            raise LclEvaluationError("LCL function recursion is prohibited", span=self.span)
        token = _ACTIVE_FUNCTIONS.set(active | {key})
        try:
            values = _bind(self.parameters, args, kwargs)
            resolver = ScopedResolver(values, self.closure)
            return await self._evaluate(self.body, resolver)
        finally:
            _ACTIVE_FUNCTIONS.reset(token)


async def _create_function(
    node: LclFunction,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> LclFunctionValue:
    """Create a closure and resolve its parameter defaults.

    :param node: Function AST node to turn into a callable value.
    :param resolver: Defining resolver retained as the lexical closure.
    :param evaluate: Recursive evaluator used for default expressions.
    :returns: Immutable callable closure with bound parameter metadata.
    .. note:: Defaults are evaluated once during creation rather than on each call.
    """
    parameters: list[_BoundParameter] = []
    for parameter in node.parameters:
        default = await _default(parameter, resolver, evaluate)
        parameters.append(_BoundParameter(str(parameter.name), parameter.kind, default))
    return LclFunctionValue(tuple(parameters), node.body, resolver, node.span, evaluate)


async def _default(
    parameter: LclParameter,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Resolve one parameter default or return the missing sentinel.
    :param parameter: Parameter whose optional default should be evaluated.
    :param resolver: Resolver used by the default expression.
    :param evaluate: Recursive evaluator for the default expression.
    :returns: Evaluated default value, or ``_MISSING`` when absent.
    .. note:: The sentinel distinguishes an omitted default from an explicit ``None``.
    """
    if parameter.default is None:
        return _MISSING
    return await evaluate(parameter.default, resolver)


def _bind(
    parameters: tuple[_BoundParameter, ...],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> dict[str, object]:
    """Bind positional, variadic, keyword-only, and named arguments.

    :param parameters: Ordered normalized parameter rules.
    :param args: Positional call arguments.
    :param kwargs: Named call arguments.
    :returns: Local name-to-value bindings for one invocation.
    :raises TypeError: If arguments are duplicated, missing, unexpected, or exceed the available positional parameters.
    .. note:: Named arguments are copied before binding, so caller-owned input is not mutated.
    """
    values: dict[str, object] = {}
    named = dict(kwargs)
    position = 0
    variadic_position = False
    variadic_keyword = False
    for parameter in parameters:
        if parameter.kind is ParameterKind.POSITIONAL:
            position = _bind_positional(parameter, args, position, named, values)
        elif parameter.kind is ParameterKind.VAR_POSITIONAL:
            values[parameter.name] = args[position:]
            position = len(args)
            variadic_position = True
        elif parameter.kind is ParameterKind.KEYWORD_ONLY:
            values[parameter.name] = _take_named(parameter, named)
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


def _bind_positional(
    parameter: _BoundParameter,
    args: tuple[object, ...],
    position: int,
    named: dict[str, object],
    values: dict[str, object],
) -> int:
    """Bind one ordinary positional parameter and advance the cursor.

    :param parameter: Positional parameter rule to satisfy.
    :param args: Positional call arguments.
    :param position: Current zero-based positional cursor.
    :param named: Remaining named arguments, including possible overrides.
    :param values: Binding map being populated for the invocation.
    :returns: Cursor after consuming a positional argument, or unchanged when a named argument or default supplies the value.
    :raises TypeError: If the parameter is duplicated or has no supplied value or default.
    .. note:: Exhausted positional arguments use named binding and default rules.
    """
    if position < len(args):
        if parameter.name in named:
            raise TypeError(f"multiple values for argument: {parameter.name}")
        values[parameter.name] = args[position]
        return position + 1
    values[parameter.name] = _take_named(parameter, named)
    return position


def _take_named(
    parameter: _BoundParameter,
    named: dict[str, object],
) -> object:
    """Consume a named argument or provide its default value.

    :param parameter: Parameter whose name and default should be consulted.
    :param named: Mutable remaining named-argument mapping.
    :returns: Popped argument value or the parameter's default.
    :raises TypeError: If the parameter is required but no value was supplied.
    .. note:: Successful lookup removes the entry, allowing unexpected keywords to be detected later.
    """
    if parameter.name in named:
        return named.pop(parameter.name)
    if parameter.default is not _MISSING:
        return parameter.default
    raise TypeError(f"missing required argument: {parameter.name}")
