"""Async AST interpretation used by the Frame runtime.

Defines ``interpret_expression``, ``internal_coerce_resolver``, ``internal_evaluate``,
``internal_evaluate_node``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sized
from typing import Literal, cast

from lclang.common.awaitable_resolution import resolve_awaitable
from lclang.error import LanguageErrorCode, LclError, LclEvaluationError
from lclang.error.operation_guard import guard_async_failure
from lclang.error.verbose_diagnostic import (
    internal_render_value,
    internal_trace,
    internal_verbose_enabled,
)
from lclang.lang.ast import (
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
    LclRecordDisplay,
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
from lclang.lang.ast.operator_nodes import UnaryOperator
from lclang.lang.common.binding_declaration import get_override_marker
from lclang.lang.engine.evaluator.call_evaluation import internal_evaluate_call
from lclang.lang.engine.evaluator.collection_evaluation import internal_evaluate_display
from lclang.lang.engine.evaluator.comprehension_evaluation import internal_evaluate_comprehension
from lclang.lang.engine.evaluator.context_manager_evaluation import internal_evaluate_with
from lclang.lang.engine.evaluator.definition_scope import active_definition_stack
from lclang.lang.engine.evaluator.error_form_evaluation import (
    internal_evaluate_error_form,
    internal_wrap_failure,
)
from lclang.lang.engine.evaluator.evaluation_budget import (
    internal_check_collection,
    internal_enter_node,
    internal_leave_node,
)
from lclang.lang.engine.evaluator.evaluation_journal import (
    ACTIVE_TARGET_EXPRESSION,
    capture_evaluation_context,
    collect_evaluation_context,
    record_value_read,
)
from lclang.lang.engine.evaluator.fstring_evaluation import internal_evaluate_joined
from lclang.lang.engine.evaluator.lcl_function import create_function
from lclang.lang.engine.evaluator.logical_evaluation import internal_evaluate_logical
from lclang.lang.engine.evaluator.name_resolver import MappingResolver, Resolver
from lclang.lang.engine.evaluator.operator_evaluation import internal_evaluate_operation
from lclang.lang.engine.evaluator.primary_evaluation import internal_evaluate_primary
from lclang.lang.engine.printer import to_source

type ResolverSource = Resolver | Mapping[str, object] | None


@guard_async_failure(LclEvaluationError, LanguageErrorCode.E39_AST_INTERPRETATION_NATIVE_FAILURE)
async def interpret_expression(node: LclAstNode, resolver: ResolverSource = None) -> object:
    """Interpret one AST for the Frame runtime and language subsystem.

    :param node: Semantic AST root to evaluate.
    :param resolver: Optional resolver or string-keyed value mapping.
    :returns: Fully resolved immediate result value.
    :raises LclNameError: If a mapping-backed variable is missing.
    :raises LclEvaluationError: If evaluation or an application protocol fails.

    .. note::
       Structured LCL failures pass unchanged; ordinary failures are wrapped and
       every result is recursively auto-awaited.
    """
    try:
        name = active_definition_stack()[-1] if active_definition_stack() else "<expr>"
        kind: Literal["definition", "function", "target"] = (
            "target" if node is ACTIVE_TARGET_EXPRESSION.get() else "definition"
        )
        with collect_evaluation_context(name, node, kind=kind):
            result = await internal_evaluate(node, internal_coerce_resolver(resolver))
    except BaseException as error:
        if internal_verbose_enabled():
            definition = " -> ".join(active_definition_stack()) or "<direct>"
            internal_trace(
                "evaluate",
                f"definition={definition!r} "
                f"expression={internal_render_value(node, lambda: to_source(node))} "
                f"error={internal_render_value(error)}",
            )
        raise
    if internal_verbose_enabled():
        definition = " -> ".join(active_definition_stack()) or "<direct>"
        internal_trace(
            "evaluate",
            f"definition={definition!r} "
            f"expression={internal_render_value(node, lambda: to_source(node))} "
            f"result={internal_render_value(result)}",
        )
    return result


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
        if error.span is None:
            error.span = node.span
        error.attach_variable_stack(active_definition_stack())
        if not error.evaluation_context:
            error.attach_evaluation_context(capture_evaluation_context())
        raise
    except Exception as error:
        wrapped = internal_wrap_failure(error, node.span, node=node)
        wrapped.attach_variable_stack(active_definition_stack())
        wrapped.attach_evaluation_context(capture_evaluation_context())
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
        if get_override_marker(node) is not None:
            name = active_definition_stack()[-1] if active_definition_stack() else "<expr>"
            raise LclEvaluationError(
                f"{name} needs a value",
                span=node.span,
                code=LanguageErrorCode.E39_EXPRESSION_VALUE_REQUIRED,
            )
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
    elif isinstance(node, (LclTuple, LclList, LclSet, LclDict, LclRecordDisplay)):
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
        raise LclEvaluationError(
            f"unsupported AST node: {name}",
            span=node.span,
            code=LanguageErrorCode.E39_UNSUPPORTED_AST_NODE,
        )
    resolved = await resolve_awaitable(result)
    if isinstance(node, LclName):
        record_value_read(str(node.identifier), resolved, node.span)
    if isinstance(node, LclRecordDisplay):
        internal_check_collection(len(node.fields), node.span)
    elif isinstance(
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
