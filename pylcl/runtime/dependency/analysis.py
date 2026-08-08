"""Pure scope-aware static dependency analysis over semantic AST."""

from __future__ import annotations

from pylcl.ast import (
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
from pylcl.runtime.dependency.model import DependencyKind, DependencyReference

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
    _visit(node, DependencyKind.EAGER, frozenset(), references)
    return tuple(references)


def _visit(
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
                _visit(parameter.default, kind, bound, references)
        names = frozenset(str(parameter.name) for parameter in node.parameters)
        _visit(node.body, _weaken(kind, DependencyKind.DEFERRED), bound | names, references)
        return
    if isinstance(
        node,
        (LclGenerator, LclListComprehension, LclSetComprehension, LclDictComprehension),
    ):
        _visit_comprehension(node, kind, bound, references)
        return
    if isinstance(node, LclBoolean):
        _visit(node.values[0], kind, bound, references)
        conditional = _weaken(kind, DependencyKind.CONDITIONAL)
        for value in node.values[1:]:
            _visit(value, conditional, bound, references)
        return
    if isinstance(node, LclCoalesce):
        _visit(node.left, kind, bound, references)
        _visit(node.right, _weaken(kind, DependencyKind.CONDITIONAL), bound, references)
        return
    if isinstance(node, LclConditional):
        _visit(node.condition, kind, bound, references)
        branch = _weaken(kind, DependencyKind.CONDITIONAL)
        _visit(node.when_true, branch, bound, references)
        _visit(node.when_false, branch, bound, references)
        return
    if isinstance(node, LclCompare):
        _visit(node.left, kind, bound, references)
        _visit(node.comparators[0], kind, bound, references)
        later = _weaken(kind, DependencyKind.CONDITIONAL)
        for comparator in node.comparators[1:]:
            _visit(comparator, later, bound, references)
        return
    if isinstance(node, LclAssert):
        _visit(node.condition, kind, bound, references)
        if node.message is not None:
            _visit(node.message, _weaken(kind, DependencyKind.CONDITIONAL), bound, references)
        return
    if isinstance(node, LclTry):
        _visit_try(node, kind, bound, references)
        return
    if isinstance(node, LclWith):
        scope = bound
        for item in node.items:
            _visit(item.context, kind, scope, references)
            if item.target is not None:
                scope = scope | {str(item.target)}
        _visit(node.body, kind, scope, references)
        return
    for child in node.children():
        _visit(child, kind, bound, references)


def _visit_comprehension(
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
        kind = _weaken(kind, DependencyKind.DEFERRED)
    scope = bound
    for index, clause in enumerate(node.clauses):
        clause_kind = kind if index == 0 else _weaken(kind, DependencyKind.CONDITIONAL)
        _visit(clause.iterable, clause_kind, scope, references)
        scope = scope | {str(clause.target.identifier)}
        filtered = _weaken(kind, DependencyKind.CONDITIONAL)
        for condition in clause.conditions:
            _visit(condition, filtered, scope, references)
    output_kind = kind if isinstance(node, LclGenerator) else _weaken(
        kind,
        DependencyKind.CONDITIONAL,
    )
    head = node.entry if isinstance(node, LclDictComprehension) else node.element
    _visit(head, output_kind, scope, references)


def _visit_try(
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
    _visit(node.body, kind, bound, references)
    handler_kind = _weaken(kind, DependencyKind.CONDITIONAL)
    for handler in node.handlers:
        _visit_handler(handler, handler_kind, bound, references)
    if node.finally_body is not None:
        _visit(node.finally_body, kind, bound, references)


def _visit_handler(
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
        _visit(handler.exception, kind, bound, references)
    scope = bound if handler.name is None else bound | {str(handler.name)}
    _visit(handler.body, kind, scope, references)


def _weaken(current: DependencyKind, requested: DependencyKind) -> DependencyKind:
    """Select the less eager of two dependency classifications.

    :param current: Classification inherited from the enclosing expression.
    :param requested: Minimum laziness introduced by the current construct.
    :returns: Weaker classification according to the stable strength table.
    """
    return max((current, requested), key=_STRENGTH.__getitem__)
