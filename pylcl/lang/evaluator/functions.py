"""Function creation, argument binding, closures, and recursion control."""

from __future__ import annotations

from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import dataclass

from pylcl.ast import LclAstNode, LclFunction
from pylcl.errors import LclEvaluationError
from pylcl.lang.evaluator._types import EvaluateNode
from pylcl.lang.evaluator.context import Resolver, ScopedResolver
from pylcl.lang.evaluator.definition_context import active_definition, definition_scope
from pylcl.lang.evaluator.function_arguments import (
    BoundParameter,
    bind_arguments,
    resolve_default,
)
from pylcl.lang.printer import to_source
from pylcl.source import SourceSpan

# Active closure identities used for same-task recursion rejection.
_ACTIVE_FUNCTIONS: ContextVar[frozenset[int]] = ContextVar(
    "pylcl_active_functions",
    default=frozenset(),
)


@dataclass(frozen=True, slots=True)
class LclFunctionValue:
    """Represent one callable LCL closure.

    :param parameters: Parameters with defaults resolved at creation time.
    :param body: Semantic AST expression evaluated on every call.
    :param closure: Defining resolver used beneath invocation locals.
    :param span: Function source range used for recursion diagnostics.
    :param definition_name: Optional lexical Frame definition owner.
    :param source: Original function node retained for canonical representation.

    .. note::
       Calls are async, task-safe, and deliberately non-recursive in LCL V1.
    """

    parameters: tuple[BoundParameter, ...]
    body: LclAstNode
    closure: Resolver
    span: SourceSpan
    definition_name: str | None
    source: LclFunction
    _evaluate: EvaluateNode

    def __repr__(self) -> str:
        """Return the canonical LCL function expression.

        :returns: Source-oriented function representation without closure internals.
        """
        return to_source(self.source)

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
            values = bind_arguments(self.parameters, args, kwargs)
            resolver = ScopedResolver(values, self.closure)
            scope = (
                definition_scope(self.definition_name)
                if self.definition_name is not None
                else nullcontext()
            )
            with scope:
                return await self._evaluate(self.body, resolver)
        finally:
            _ACTIVE_FUNCTIONS.reset(token)


async def create_function(
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
    parameters: list[BoundParameter] = []
    for parameter in node.parameters:
        default = await resolve_default(parameter, resolver, evaluate)
        parameters.append(BoundParameter(str(parameter.name), parameter.kind, default))
    return LclFunctionValue(
        tuple(parameters),
        node.body,
        resolver,
        node.span,
        active_definition(),
        node,
        evaluate,
    )
