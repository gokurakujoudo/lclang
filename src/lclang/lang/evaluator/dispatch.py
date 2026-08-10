"""Public async evaluation dispatch and synchronous convenience boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sized
from typing import cast

from lclang.ast import (
    LclAssert,
    LclAstNode,
    LclAttribute,
    LclBinary,
    LclBoolean,
    LclCall,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclConstant,
    LclDict,
    LclDictComprehension,
    LclFunction,
    LclGenerator,
    LclJoinedString,
    LclList,
    LclListComprehension,
    LclName,
    LclRaise,
    LclSafeAttribute,
    LclSet,
    LclSetComprehension,
    LclSlice,
    LclSubscript,
    LclTry,
    LclTuple,
    LclUnary,
    LclWith,
)
from lclang.ast.operators import UnaryOperator
from lclang.errors import LclError, LclEvaluationError
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.lang.evaluator.budget import (
    internal_check_collection,
    internal_enter_node,
    internal_leave_node,
)
from lclang.lang.evaluator.calls import internal_evaluate_call
from lclang.lang.evaluator.comprehensions import internal_evaluate_comprehension
from lclang.lang.evaluator.context import MappingResolver, Resolver
from lclang.lang.evaluator.contexts import internal_evaluate_with
from lclang.lang.evaluator.definition_context import active_definition_stack
from lclang.lang.evaluator.displays import internal_evaluate_display
from lclang.lang.evaluator.errors import internal_evaluate_error_form, internal_wrap_failure
from lclang.lang.evaluator.fstrings import internal_evaluate_joined
from lclang.lang.evaluator.functions import create_function
from lclang.lang.evaluator.logical import internal_evaluate_logical
from lclang.lang.evaluator.operations import internal_evaluate_operation
from lclang.lang.evaluator.primaries import internal_evaluate_primary

type ResolverSource = Resolver | Mapping[str, object] | None


async def evaluate(node: LclAstNode, resolver: ResolverSource = None) -> object:
    """Evaluate one AST using an async resolver boundary.

    :param node: Semantic AST root to evaluate.
    :param resolver: Optional resolver or string-keyed value mapping.
    :returns: Fully resolved immediate result value.
    :raises LclNameError: If a mapping-backed variable is missing.
    :raises LclEvaluationError: If evaluation or an application protocol fails.

    .. note::
       Structured LCL failures pass unchanged; ordinary failures are wrapped and
       every result is recursively auto-awaited.
    """
    return await internal_evaluate(node, internal_coerce_resolver(resolver))


def internal_coerce_resolver(source: ResolverSource) -> Resolver:
    """Normalize public resolver input to the internal resolver protocol.

    :param source: Optional resolver, string-keyed mapping, or ``None``.
    :returns: Resolver used by the recursive evaluator.

    .. note::
       ``None`` becomes an empty mapping resolver; supplied mappings are
       adapted without copying their values.
    """
    if source is None:
        return MappingResolver({})
    if isinstance(source, Mapping):
        return MappingResolver(source)
    return source


async def internal_evaluate(node: LclAstNode, resolver: Resolver) -> object:
    """Evaluate one node within the failure and budget boundaries.

    :param node: AST node to evaluate.
    :param resolver: Resolver supplying names referenced by the node.
    :returns: Fully resolved immediate result value.
    :raises LclError: Structured LCL failures propagate unchanged.
    :raises LclEvaluationError: Ordinary failures are wrapped with the node's source span.
    :raises LclEvaluationError: If failure wrapping produces the raised error.

    .. note::
       Node-entry depth is restored in ``finally`` even when evaluation raises
       or is cancelled.
    """
    token = None
    try:
        token = internal_enter_node(node.span)
        return await internal_evaluate_node(node, resolver)
    except LclError as error:
        error.attach_variable_stack(active_definition_stack())
        raise
    except Exception as error:
        wrapped = internal_wrap_failure(error, node.span)
        wrapped.attach_variable_stack(active_definition_stack())
        raise wrapped from error
    finally:
        internal_leave_node(token)


async def internal_evaluate_node(node: LclAstNode, resolver: Resolver) -> object:
    """Dispatch a node to its specialized evaluator and resolve its result.

    :param node: AST node whose concrete form selects an evaluator branch.
    :param resolver: Resolver supplying names referenced by the node.
    :returns: Fully resolved immediate result after recursive awaiting.
    :raises LclEvaluationError: If the node type is unsupported.

    .. note::
       Collection limits are checked only after collection values are fully
       materialized, while all other values pass directly through unchanged.
    """
    if isinstance(node, LclConstant):
        result = node.value
    elif isinstance(node, LclName):
        result = await resolver.resolve(node.identifier, span=node.span)
    elif isinstance(node, (LclAttribute, LclSafeAttribute, LclSubscript, LclSlice)):
        result = await internal_evaluate_primary(node, resolver, internal_evaluate)
    elif isinstance(node, LclCall):
        result = await internal_evaluate_call(node, resolver, internal_evaluate)
    elif isinstance(node, LclFunction):
        result = await create_function(node, resolver, internal_evaluate)
    elif isinstance(node, (LclRaise, LclAssert, LclTry)):
        result = await internal_evaluate_error_form(node, resolver, internal_evaluate)
    elif isinstance(node, LclWith):
        result = await internal_evaluate_with(node, resolver, internal_evaluate)
    elif isinstance(node, LclJoinedString):
        result = await internal_evaluate_joined(node, resolver, internal_evaluate)
    elif isinstance(node, (LclTuple, LclList, LclSet, LclDict)):
        result = await internal_evaluate_display(node, resolver, internal_evaluate)
    elif isinstance(
        node,
        (LclGenerator, LclListComprehension, LclSetComprehension, LclDictComprehension),
    ):
        result = await internal_evaluate_comprehension(node, resolver, internal_evaluate)
    elif isinstance(node, (LclBoolean, LclCoalesce, LclConditional)) or (
        isinstance(node, LclUnary) and node.operator is UnaryOperator.NOT
    ):
        result = await internal_evaluate_logical(node, resolver, internal_evaluate)
    elif isinstance(node, (LclBinary, LclCompare)) or (
        isinstance(node, LclUnary) and node.operator is not UnaryOperator.NOT
    ):
        result = await internal_evaluate_operation(node, resolver, internal_evaluate)
    else:
        name = type(node).__name__
        raise LclEvaluationError(f"unsupported AST node: {name}", span=node.span)
    resolved = await resolve_awaitable(result)
    if isinstance(
        node,
        (
            LclTuple,
            LclList,
            LclSet,
            LclDict,
            LclListComprehension,
            LclSetComprehension,
            LclDictComprehension,
        ),
    ):
        internal_check_collection(len(cast(Sized, resolved)), node.span)
    return resolved
