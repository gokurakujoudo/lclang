"""Public async evaluation dispatch and synchronous convenience boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sized
from typing import cast

from pylcl.ast import (
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
from pylcl.ast.operators import UnaryOperator
from pylcl.errors import LclError, LclEvaluationError
from pylcl.lang.evaluator.awaitables import resolve_awaitable
from pylcl.lang.evaluator.budget import _check_collection, _enter_node, _leave_node
from pylcl.lang.evaluator.calls import _evaluate_call
from pylcl.lang.evaluator.comprehensions import _evaluate_comprehension
from pylcl.lang.evaluator.context import MappingResolver, Resolver
from pylcl.lang.evaluator.contexts import _evaluate_with
from pylcl.lang.evaluator.definition_context import active_definition_stack
from pylcl.lang.evaluator.displays import _evaluate_display
from pylcl.lang.evaluator.errors import _evaluate_error_form, _wrap_failure
from pylcl.lang.evaluator.fstrings import _evaluate_joined
from pylcl.lang.evaluator.functions import create_function
from pylcl.lang.evaluator.logical import _evaluate_logical
from pylcl.lang.evaluator.operations import _evaluate_operation
from pylcl.lang.evaluator.primaries import _evaluate_primary

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
    return await _evaluate(node, _coerce_resolver(resolver))


def _coerce_resolver(source: ResolverSource) -> Resolver:
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


async def _evaluate(node: LclAstNode, resolver: Resolver) -> object:
    """Evaluate one node within the failure and budget boundaries.

    :param node: AST node to evaluate.
    :param resolver: Resolver supplying names referenced by the node.
    :returns: Fully resolved immediate result value.
    :raises LclError: Structured LCL failures propagate unchanged.
    :raises LclEvaluationError: Ordinary failures are wrapped with the node's source span.
    :raises _wrap_failure: If failure wrapping produces the raised error.

    .. note::
       Node-entry depth is restored in ``finally`` even when evaluation raises
       or is cancelled.
    """
    token = None
    try:
        token = _enter_node(node.span)
        return await _evaluate_node(node, resolver)
    except LclError as error:
        error.attach_variable_stack(active_definition_stack())
        raise
    except Exception as error:
        wrapped = _wrap_failure(error, node.span)
        wrapped.attach_variable_stack(active_definition_stack())
        raise wrapped from error
    finally:
        _leave_node(token)


async def _evaluate_node(node: LclAstNode, resolver: Resolver) -> object:
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
        result = await _evaluate_primary(node, resolver, _evaluate)
    elif isinstance(node, LclCall):
        result = await _evaluate_call(node, resolver, _evaluate)
    elif isinstance(node, LclFunction):
        result = await create_function(node, resolver, _evaluate)
    elif isinstance(node, (LclRaise, LclAssert, LclTry)):
        result = await _evaluate_error_form(node, resolver, _evaluate)
    elif isinstance(node, LclWith):
        result = await _evaluate_with(node, resolver, _evaluate)
    elif isinstance(node, LclJoinedString):
        result = await _evaluate_joined(node, resolver, _evaluate)
    elif isinstance(node, (LclTuple, LclList, LclSet, LclDict)):
        result = await _evaluate_display(node, resolver, _evaluate)
    elif isinstance(
        node,
        (LclGenerator, LclListComprehension, LclSetComprehension, LclDictComprehension),
    ):
        result = await _evaluate_comprehension(node, resolver, _evaluate)
    elif isinstance(node, (LclBoolean, LclCoalesce, LclConditional)) or (
        isinstance(node, LclUnary) and node.operator is UnaryOperator.NOT
    ):
        result = await _evaluate_logical(node, resolver, _evaluate)
    elif isinstance(node, (LclBinary, LclCompare)) or (
        isinstance(node, LclUnary) and node.operator is not UnaryOperator.NOT
    ):
        result = await _evaluate_operation(node, resolver, _evaluate)
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
        _check_collection(len(cast(Sized, resolved)), node.span)
    return resolved
