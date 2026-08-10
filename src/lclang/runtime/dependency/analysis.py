"""Pure scope-aware static dependency analysis over semantic AST."""

from __future__ import annotations

from lclang.ast import (
    LclAssert,
    LclAstNode,
    LclBoolean,
    LclCoalesce,
    LclCompare,
    LclConditional,
    LclDictComprehension,
    LclExceptHandler,
    LclFunction,
    LclGenerator,
    LclListComprehension,
    LclName,
    LclSetComprehension,
    LclTry,
    LclWith,
)
from lclang.runtime.dependency.model import DependencyKind, DependencyReference

type Comprehension = (
    LclGenerator | LclListComprehension | LclSetComprehension | LclDictComprehension
)

_STRENGTH = {
    DependencyKind.EAGER: 0,
    DependencyKind.CONDITIONAL: 1,
    DependencyKind.DEFERRED: 2,
    DependencyKind.DYNAMIC: 3,
}


def analyze_dependencies(node: LclAstNode) -> tuple[DependencyReference, ...]:
    """Return scope-aware free-name occurrences in runtime evaluation order.

    :param node: Semantic AST root to inspect without evaluation.
    :returns: Ordered immutable dependency-reference occurrences.

    .. note::
       Attribute names, keyword labels, and lexical binding sites are excluded.
    """
    references: list[DependencyReference] = []
    internal_visit(node, DependencyKind.EAGER, frozenset(), references)
    return tuple(references)


def internal_visit(
    node: LclAstNode,
    kind: DependencyKind,
    bound: frozenset[str],
    references: list[DependencyReference],
) -> None:
    """Append free-name occurrences from one node in evaluation order.

    :param node: AST node currently being traversed.
    :param kind: Strongest dependency classification inherited by the node.
    :param bound: Lexically bound names excluded from free references.
    :param references: Mutable ordered result accumulator.
    """
    if isinstance(node, LclName):
        if str(node.identifier) not in bound:
            references.append(DependencyReference(node.identifier, kind, node.span))
        return
    if isinstance(node, LclFunction):
        for parameter in node.parameters:
            if parameter.default is not None:
                internal_visit(parameter.default, kind, bound, references)
        names = frozenset(str(parameter.name) for parameter in node.parameters)
        internal_visit(
            node.body, internal_weaken(kind, DependencyKind.DEFERRED), bound | names, references
        )
        return
    if isinstance(
        node,
        (LclGenerator, LclListComprehension, LclSetComprehension, LclDictComprehension),
    ):
        internal_visit_comprehension(node, kind, bound, references)
        return
    if isinstance(node, LclBoolean):
        internal_visit(node.values[0], kind, bound, references)
        conditional = internal_weaken(kind, DependencyKind.CONDITIONAL)
        for value in node.values[1:]:
            internal_visit(value, conditional, bound, references)
        return
    if isinstance(node, LclCoalesce):
        internal_visit(node.left, kind, bound, references)
        internal_visit(
            node.right, internal_weaken(kind, DependencyKind.CONDITIONAL), bound, references
        )
        return
    if isinstance(node, LclConditional):
        internal_visit(node.condition, kind, bound, references)
        branch = internal_weaken(kind, DependencyKind.CONDITIONAL)
        internal_visit(node.when_true, branch, bound, references)
        internal_visit(node.when_false, branch, bound, references)
        return
    if isinstance(node, LclCompare):
        internal_visit(node.left, kind, bound, references)
        internal_visit(node.comparators[0], kind, bound, references)
        later = internal_weaken(kind, DependencyKind.CONDITIONAL)
        for comparator in node.comparators[1:]:
            internal_visit(comparator, later, bound, references)
        return
    if isinstance(node, LclAssert):
        internal_visit(node.condition, kind, bound, references)
        if node.message is not None:
            internal_visit(
                node.message, internal_weaken(kind, DependencyKind.CONDITIONAL), bound, references
            )
        return
    if isinstance(node, LclTry):
        internal_visit_try(node, kind, bound, references)
        return
    if isinstance(node, LclWith):
        scope = bound
        for item in node.items:
            internal_visit(item.context, kind, scope, references)
            if item.target is not None:
                scope = scope | {str(item.target)}
        internal_visit(node.body, kind, scope, references)
        return
    for child in node.children():
        internal_visit(child, kind, bound, references)


def internal_visit_comprehension(
    node: Comprehension,
    kind: DependencyKind,
    bound: frozenset[str],
    references: list[DependencyReference],
) -> None:
    """Visit comprehension clauses with their evolving lexical scope.

    :param node: Generator or materialized comprehension node.
    :param kind: Classification inherited from the enclosing expression.
    :param bound: Names bound outside the comprehension.
    :param references: Mutable ordered result accumulator.
    """
    if isinstance(node, LclGenerator):
        kind = internal_weaken(kind, DependencyKind.DEFERRED)
    scope = bound
    for index, clause in enumerate(node.clauses):
        clause_kind = kind if index == 0 else internal_weaken(kind, DependencyKind.CONDITIONAL)
        internal_visit(clause.iterable, clause_kind, scope, references)
        scope = scope | {str(clause.target.identifier)}
        filtered = internal_weaken(kind, DependencyKind.CONDITIONAL)
        for condition in clause.conditions:
            internal_visit(condition, filtered, scope, references)
    output_kind = (
        kind
        if isinstance(node, LclGenerator)
        else internal_weaken(
            kind,
            DependencyKind.CONDITIONAL,
        )
    )
    head = node.entry if isinstance(node, LclDictComprehension) else node.element
    internal_visit(head, output_kind, scope, references)


def internal_visit_try(
    node: LclTry,
    kind: DependencyKind,
    bound: frozenset[str],
    references: list[DependencyReference],
) -> None:
    """Visit protected, handler, and finalizer expressions.

    :param node: Try expression to inspect.
    :param kind: Classification inherited from the enclosing expression.
    :param bound: Names bound outside the try expression.
    :param references: Mutable ordered result accumulator.
    """
    internal_visit(node.body, kind, bound, references)
    handler_kind = internal_weaken(kind, DependencyKind.CONDITIONAL)
    for handler in node.handlers:
        internal_visit_handler(handler, handler_kind, bound, references)
    if node.finally_body is not None:
        internal_visit(node.finally_body, kind, bound, references)


def internal_visit_handler(
    handler: LclExceptHandler,
    kind: DependencyKind,
    bound: frozenset[str],
    references: list[DependencyReference],
) -> None:
    """Visit one exception handler with its optional local binding.

    :param handler: Handler expression to inspect.
    :param kind: Conditional classification selected for handlers.
    :param bound: Names bound outside the handler.
    :param references: Mutable ordered result accumulator.
    """
    if handler.exception is not None:
        internal_visit(handler.exception, kind, bound, references)
    scope = bound if handler.name is None else bound | {str(handler.name)}
    internal_visit(handler.body, kind, scope, references)


def internal_weaken(current: DependencyKind, requested: DependencyKind) -> DependencyKind:
    """Select the less eager of two dependency classifications.

    :param current: Classification inherited from the enclosing expression.
    :param requested: Minimum laziness introduced by the current construct.
    :returns: Weaker classification according to the stable strength table.
    """
    return max((current, requested), key=_STRENGTH.__getitem__)
