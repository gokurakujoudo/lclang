"""Function creation, argument binding, closures, and recursion control.

Defines ``LclFunctionValue``, ``create_function``.
"""

from __future__ import annotations

from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import dataclass

from lclang.common.source_location import SourceSpan
from lclang.error import LanguageErrorCode, LclEvaluationError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor
from lclang.error.verbose_diagnostic import ACTIVE_MASKED_VALUE, internal_masked_scope
from lclang.lang.ast import LclAstNode, LclFunction
from lclang.lang.engine.evaluator.definition_scope import active_definition, definition_scope
from lclang.lang.engine.evaluator.evaluation_callback import EvaluateNode
from lclang.lang.engine.evaluator.evaluation_journal import collect_evaluation_context
from lclang.lang.engine.evaluator.function_arguments import (
    BoundParameter,
    bind_arguments,
    resolve_default,
)
from lclang.lang.engine.evaluator.name_resolver import Resolver, ScopedResolver
from lclang.lang.engine.printer import to_source

# Active closure identities used for same-task recursion rejection.
# Unitless context key names identify active LCL calls within a task. An empty initial path
# avoids shared global recursion state; entries retain structured recursive-call diagnostics.
_ACTIVE_FUNCTIONS: ContextVar[frozenset[int]] = ContextVar(
    "lclang_active_functions",
    default=frozenset(),
)


@guard_constructor(
    LclValidationError, LanguageErrorCode.E37_LCL_FUNCTION_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True, weakref_slot=True)
class LclFunctionValue:
    """Represent one callable LCL closure.

    :param parameters: Parameters with defaults resolved at creation time.
    :param body: Semantic AST expression evaluated on every call.
    :param closure: Defining resolver used beneath invocation locals.
    :param span: Function source range used for recursion diagnostics.
    :param definition_name: Optional lexical Frame definition owner.
    :param source: Original function node retained for canonical representation.
    :param internal_evaluate: Recursive evaluator retained by the closure.
    :param masked: Whether the defining name protects invocation diagnostics.

    .. note::
       Calls are async, task-safe, and deliberately non-recursive in LCL V1.
    """

    parameters: tuple[BoundParameter, ...]
    body: LclAstNode
    closure: Resolver
    span: SourceSpan
    definition_name: str | None
    source: LclFunction
    internal_evaluate: EvaluateNode
    masked: bool = False

    def __repr__(self) -> str:
        """Return the canonical LCL function expression.

        :returns: Source-oriented function representation without closure internals.
        """
        return to_source(self.source)

    @guard_async_failure(
        LclEvaluationError, LanguageErrorCode.E37_LCL_FUNCTION_CONSTRUCTION_NATIVE_FAILURE
    )
    async def __call__(self, *args: object, **kwargs: object) -> object:
        """Bind arguments and evaluate the body in the lexical closure.

        :param args: Positional application values.
        :param kwargs: Named application values.
        :returns: Fully evaluated function body result.
        :raises LclValidationError: If arguments do not satisfy the parameter contract.
        :raises LclEvaluationError: If this value re-enters in the same task.

        .. note::
           Concurrent calls in distinct tasks have independent recursion state.
        """
        key = id(self)
        active = _ACTIVE_FUNCTIONS.get()
        if key in active:
            raise LclEvaluationError(
                "LCL function recursion is prohibited",
                span=self.span,
                code=LanguageErrorCode.E37_LCL_FUNCTION_RECURSION_IS_PROHIBITED,
            )
        token = _ACTIVE_FUNCTIONS.set(active | {key})
        try:
            values = bind_arguments(self.parameters, args, kwargs)
            resolver = ScopedResolver(values, self.closure)
            scope = (
                definition_scope(self.definition_name)
                if self.definition_name is not None
                else nullcontext()
            )
            with (
                scope,
                internal_masked_scope(self.masked),
                collect_evaluation_context(
                    self.definition_name or "<function>", self.body, kind="function"
                ),
            ):
                return await self.internal_evaluate(self.body, resolver)
        finally:
            _ACTIVE_FUNCTIONS.reset(token)


@guard_async_failure(
    LclEvaluationError, LanguageErrorCode.E37_LCL_FUNCTION_CONSTRUCTION_NATIVE_FAILURE
)
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
        ACTIVE_MASKED_VALUE.get(),
    )
