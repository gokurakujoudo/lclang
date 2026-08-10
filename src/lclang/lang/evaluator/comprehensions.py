"""Scoped sync/async comprehension and lazy generator evaluation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import cast

from lclang.ast import (
    LclAstNode,
    LclDictComprehension,
    LclDictUnpack,
    LclGenerator,
    LclKeyValue,
    LclListComprehension,
    LclSetComprehension,
    LclStarred,
)
from lclang.ast.comprehensions import LclComprehensionClause
from lclang.lang.evaluator._types import EvaluateNode
from lclang.lang.evaluator.context import Resolver, ScopedResolver
from lclang.lang.evaluator.iteration import iterate_values

type ComprehensionNode = (
    LclGenerator | LclListComprehension | LclSetComprehension | LclDictComprehension
)


async def internal_evaluate_comprehension(
    node: ComprehensionNode,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate a generator or materialized comprehension node.

    :param node: Comprehension AST node describing the element and clauses.
    :param resolver: Resolver providing the outer lexical scope.
    :param evaluate: Recursive evaluator for nested AST expressions.
    :returns: Lazy async iterator for generators, or materialized sequence or
       mapping for list, set, and dictionary comprehensions.

    .. note::
       Generator comprehensions defer clause and element evaluation until the
       returned iterator is consumed; other forms consume it immediately.
    """
    if isinstance(node, LclDictComprehension):
        return await internal_dictionary(node, resolver, evaluate)
    stream = internal_sequence(node.element, node.clauses, resolver, evaluate)
    if isinstance(node, LclGenerator):
        return stream
    if isinstance(node, LclListComprehension):
        return [value async for value in stream]
    return {value async for value in stream}


async def internal_sequence(
    element: LclAstNode,
    clauses: tuple[LclComprehensionClause, ...],
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> AsyncIterator[object]:
    """Yield sequence-comprehension elements for each matching scope.

    :param element: Element expression evaluated in every matching scope.
    :param clauses: Ordered generators and filters defining the comprehension.
    :param resolver: Resolver providing the outer lexical scope.
    :param evaluate: Recursive evaluator for element and starred expressions.
    :returns: Lazy async iterator of generated sequence values.

    .. note::
       A starred element is flattened through the shared sync/async iteration
       adapter, while an ordinary element contributes one yielded value.
    """
    async for scope in internal_bindings(clauses, resolver, evaluate):
        if isinstance(element, LclStarred):
            expanded = await evaluate(element.value, scope)
            async for value in iterate_values(expanded):
                yield value
        else:
            yield await evaluate(element, scope)


async def internal_dictionary(
    node: LclDictComprehension,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> dict[object, object]:
    """Materialize key-value or unpacked entries for a dictionary comprehension.

    :param node: Dictionary-comprehension AST node containing the entry form.
    :param resolver: Resolver providing the outer lexical scope.
    :param evaluate: Recursive evaluator for keys, values, and unpacked maps.
    :returns: Dictionary assembled in comprehension iteration order.
    :raises TypeError: If the head has an unsupported AST type or a
       dictionary-unpacking value is not a mapping.

    .. note::
       Later entries replace earlier values for the same key, following normal
       dictionary assignment semantics.
    """
    result: dict[object, object] = {}
    async for scope in internal_bindings(node.clauses, resolver, evaluate):
        if isinstance(node.entry, LclKeyValue):
            key = await evaluate(node.entry.key, scope)
            result[key] = await evaluate(node.entry.value, scope)
        elif isinstance(node.entry, LclDictUnpack):
            value = await evaluate(node.entry.value, scope)
            if not isinstance(value, Mapping):
                raise TypeError("dictionary unpacking requires a mapping")
            result.update(cast(Mapping[object, object], value))
        else:
            raise TypeError("unsupported dictionary comprehension entry")
    return result


async def internal_bindings(
    clauses: tuple[LclComprehensionClause, ...],
    resolver: Resolver,
    evaluate: EvaluateNode,
    index: int = 0,
) -> AsyncIterator[Resolver]:
    """Yield lexical scopes satisfying the remaining comprehension clauses.

    :param clauses: Ordered generators and filters to traverse.
    :param resolver: Resolver for the current outer or nested scope.
    :param evaluate: Recursive evaluator for iterable and condition expressions.
    :param index: Zero-based clause position from which traversal continues.
    :returns: Lazy async iterator of fully bound matching resolvers.

    .. note::
       Each binding is layered over its parent with :class:`ScopedResolver`,
       so comprehension targets do not mutate the surrounding resolver.
    """
    if index == len(clauses):
        yield resolver
        return
    clause = clauses[index]
    iterable = await evaluate(clause.iterable, resolver)
    async for item in iterate_values(iterable):
        scope = ScopedResolver({str(clause.target.identifier): item}, resolver)
        if await internal_conditions(clause, scope, evaluate):
            async for nested in internal_bindings(clauses, scope, evaluate, index + 1):
                yield nested


async def internal_conditions(
    clause: LclComprehensionClause,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> bool:
    """Evaluate one clause's filters using boolean short-circuiting.

    :param clause: Comprehension clause containing zero or more conditions.
    :param resolver: Scope in which each condition is evaluated.
    :param evaluate: Recursive evaluator for condition expressions.
    :returns: ``True`` when every condition is truthy, otherwise ``False``.

    .. note::
       Conditions stop at the first false value, so later filters are not
       evaluated for a rejected item.
    """
    for condition in clause.conditions:
        if not bool(await evaluate(condition, resolver)):
            return False
    return True
