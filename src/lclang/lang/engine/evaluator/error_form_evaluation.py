"""Structured raise, assert, try, handler, and failure wrapping behaviour.

Defines ``internal_evaluate_error_form``, ``internal_try``, ``internal_handlers``,
``internal_matches``, ``internal_wrap_failure``.
"""

from __future__ import annotations

from typing import Any, cast

from lclang.common.source_location import SourceSpan
from lclang.error import LanguageErrorCode, LclError, LclEvaluationError
from lclang.error.failure_aggregation import combine_failures
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure
from lclang.lang.ast import LclAssert, LclAstNode, LclCall, LclExceptHandler, LclRaise, LclTry
from lclang.lang.engine.evaluator.evaluation_callback import EvaluateNode
from lclang.lang.engine.evaluator.name_resolver import Resolver, ScopedResolver

type ErrorNode = LclRaise | LclAssert | LclTry


async def internal_evaluate_error_form(
    node: ErrorNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a raise, assert, or try expression node.

    :param node: Error-control AST node to evaluate.
    :param resolver: Resolver supplying names referenced by the node.
    :param evaluate: Recursive evaluator for child expressions.
    :returns: Evaluated assertion value, recovered try value, or no value when
       evaluation raises.
    :raises LclEvaluationError: If a raise expression or failed assertion
       produces an evaluation failure.
    :raises error: If a raised LCL exception is re-raised with its original
       cause.

    .. note::
       Raised exception values retain their original cause while assertion and
       try forms use the same source-aware evaluation boundary.
    """
    if isinstance(node, LclRaise):
        value = await evaluate(node.value, resolver)
        if isinstance(value, LclError):
            raise value
        if isinstance(value, BaseException) and not is_ordinary_failure(value):
            raise value
        if isinstance(value, ExceptionGroup):
            raise wrap_failure(
                cast(ExceptionGroup[Exception], value),
                LclEvaluationError,
                LanguageErrorCode.E36_EXPLICIT_RAISE,
                span=node.span,
            )
        message = str(value) or "raised LCL value"
        error = LclEvaluationError(
            message, span=node.span, code=LanguageErrorCode.E36_EXPLICIT_RAISE
        )
        if isinstance(value, BaseException):
            error.freeze_native_cause(value)
            raise error from value
        raise error
    if isinstance(node, LclAssert):
        value = await evaluate(node.condition, resolver)
        if bool(value):
            return value
        message = "LCL assertion failed"
        if node.message is not None:
            detail = await evaluate(node.message, resolver)
            message = str(detail) or message
        raise LclEvaluationError(
            message, span=node.span, code=LanguageErrorCode.E36_ASSERTION_FAILED
        )
    return await internal_try(node, resolver, evaluate)


async def internal_try(
    node: LclTry,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a try expression and always run its finalizer.

    :param node: Try-expression AST node containing body, handlers, and an
       optional finalizer.
    :param resolver: Resolver supplying names referenced by the control form.
    :param evaluate: Recursive evaluator for child expressions.
    :returns: The body result, or the result returned by the first matching
       exception handler.

    .. note::
       The finalizer is evaluated even when the body or a handler raises, so
       cleanup failures follow ordinary exception precedence.
    """
    pending: BaseException | None = None
    result: object = None
    try:
        try:
            result = await evaluate(node.body, resolver)
        except Exception as error:
            result = await internal_handlers(error, node.handlers, resolver, evaluate)
    except BaseException as error:
        pending = error
    try:
        if node.finally_body is not None:
            await evaluate(node.finally_body, resolver)
    except BaseException as cleanup:
        combined = combine_failures(pending, cleanup, code=LanguageErrorCode.E36_FINALIZER_FAILURE)
        raise combined from combined.__cause__
    if pending is not None:
        raise pending
    return result


async def internal_handlers(
    error: Exception,
    handlers: tuple[LclExceptHandler, ...],
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Find and evaluate the first handler matching an exception.

    :param error: Exception raised while evaluating the try body.
    :param handlers: Ordered exception-handler AST nodes to inspect.
    :param resolver: Resolver used to evaluate handler match expressions.
    :param evaluate: Recursive evaluator for matchers and handler bodies.
    :returns: Value produced by the selected handler body.
    :raises error: If no handler accepts the exception, the original error is
       re-raised unchanged.

    .. note::
       A handler binding is layered over the existing resolver only for that
       handler body and does not mutate the enclosing scope.
    """
    for handler in handlers:
        if handler.exception is None or await internal_matches(handler, error, resolver, evaluate):
            scope = resolver
            if handler.name is not None:
                scope = ScopedResolver({str(handler.name): error}, resolver)
            return await evaluate(handler.body, scope)
    raise error


async def internal_matches(
    handler: LclExceptHandler,
    error: Exception,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> bool:
    """Determine whether an exception handler accepts an error.

    :param handler: Handler whose exception matcher should be evaluated.
    :param error: Exception currently being dispatched.
    :param resolver: Resolver used to evaluate the handler matcher.
    :param evaluate: Recursive evaluator for the matcher expression.
    :returns: ``True`` when the handler matches the error or its cause chain;
       otherwise ``False``.

    .. note::
       A handler without an exception expression is an unconditional fallback
       and matches before any matcher evaluation occurs.
    """
    if handler.exception is None:
        return True
    matcher = await evaluate(handler.exception, resolver)
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, cast(Any, matcher)):
            return True
        current = current.__cause__
    return False


def internal_wrap_failure(
    error: Exception, span: SourceSpan, *, node: LclAstNode | None = None
) -> LclError:
    """Convert an ordinary evaluator exception into a source-aware failure.

    :param error: Original exception raised during evaluation.
    :param span: Source range associated with the failed operation.
    :param node: Optional active operation used to classify host failures.
    :returns: Evaluation error containing the original exception type and
       message at *span*.

    .. note::
       The wrapper formats the original type name and message without changing
       the original exception object.
    """
    if isinstance(node, LclCall):
        code = LanguageErrorCode.E32_HOST_CALL_FAILURE
    elif isinstance(error, ZeroDivisionError):
        code = LanguageErrorCode.E31_DIVISION_BY_ZERO
    elif isinstance(error, ArithmeticError):
        code = LanguageErrorCode.E31_ARITHMETIC_FAILURE
    elif isinstance(error, AttributeError):
        code = LanguageErrorCode.E33_MISSING_ATTRIBUTE
    elif isinstance(error, KeyError):
        code = LanguageErrorCode.E33_MISSING_KEY
    elif isinstance(error, IndexError):
        code = LanguageErrorCode.E33_INDEX_OUT_OF_RANGE
    elif isinstance(error, TypeError):
        code = LanguageErrorCode.E31_OPERATOR_TYPE
    else:
        code = LanguageErrorCode.E39_EVALUATION_NATIVE_FAILURE
    return wrap_failure(error, LclEvaluationError, code, span=span)
