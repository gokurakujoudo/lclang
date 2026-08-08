"""Immutable AST values for comprehension clauses and collection forms."""

from __future__ import annotations

from dataclasses import dataclass

from pylcl.ast.atoms import LclName
from pylcl.ast.base import LclAstNode
from pylcl.ast.displays import LclDictEntry


@dataclass(frozen=True, slots=True)
class LclComprehensionClause(LclAstNode):
    """Represent one ordered ``for`` clause and its filters.

    :param target: Name receiving each iterated value.
    :param iterable: Expression producing the source iterable.
    :param conditions: Zero or more filters in source order.

    .. note::
       Iteration may be asynchronous even though V1 has no ``async for`` syntax.
    """

    target: LclName
    iterable: LclAstNode
    conditions: tuple[LclAstNode, ...] = ()

    def children(self) -> tuple[LclAstNode, ...]:
        """Return target, iterable, then filters.

        :returns: All clause expressions in deterministic source order.

        .. note::
           Runtime traversal treats the target as a binding site.
        """
        return (self.target, self.iterable, *self.conditions)


@dataclass(frozen=True, slots=True)
class _SequenceComprehension(LclAstNode):
    """Share sequence-comprehension storage and traversal.

    :param element: Expression emitted for each accepted binding.
    :param clauses: Non-empty ordered comprehension clauses.
    :raises ValueError: If no clause is supplied.

    .. note::
       Concrete subclasses select generator, list, or set materialization.
    """

    element: LclAstNode
    clauses: tuple[LclComprehensionClause, ...]

    def __post_init__(self) -> None:
        """Require at least one iteration clause.

        :raises ValueError: If no clause is supplied.
        """
        if not self.clauses:
            raise ValueError("comprehension requires at least one for clause")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the element followed by its clauses.

        :returns: Direct children in semantic traversal order.
        """
        return (self.element, *self.clauses)


@dataclass(frozen=True, slots=True)
class LclGenerator(_SequenceComprehension):
    """Represent a lazy generator expression.

    :param element: Ordinary expression yielded for each accepted binding.
    :param clauses: Non-empty ordered comprehension clauses.
    :raises ValueError: If *clauses* is empty.

    .. note::
       Evaluation returns an async iterator in the LCL runtime.
    """


@dataclass(frozen=True, slots=True)
class LclListComprehension(_SequenceComprehension):
    """Represent a list comprehension, including iterable unpack heads.

    :param element: Ordinary or starred output expression.
    :param clauses: Non-empty ordered comprehension clauses.
    :raises ValueError: If *clauses* is empty.

    .. note::
       A starred head follows PEP 798 flattening semantics.
    """


@dataclass(frozen=True, slots=True)
class LclSetComprehension(_SequenceComprehension):
    """Represent a set comprehension, including iterable unpack heads.

    :param element: Ordinary or starred output expression.
    :param clauses: Non-empty ordered comprehension clauses.
    :raises ValueError: If *clauses* is empty.

    .. note::
       Runtime uniqueness does not alter source-order AST traversal.
    """


@dataclass(frozen=True, slots=True)
class LclDictComprehension(LclAstNode):
    """Represent key/value or mapping-unpack dictionary comprehension.

    :param entry: Explicit pair or PEP 798 mapping-unpack head.
    :param clauses: Non-empty ordered comprehension clauses.
    :raises ValueError: If *clauses* is empty.

    .. note::
       Mapping unpack expansion occurs once per accepted binding.
    """

    entry: LclDictEntry
    clauses: tuple[LclComprehensionClause, ...]

    def __post_init__(self) -> None:
        """Enforce comprehension-clause cardinality.

        :raises ValueError: If no clause is supplied.
        """
        if not self.clauses:
            raise ValueError("dict comprehension requires at least one for clause")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return entry then ordered clauses.

        :returns: Head entry followed by every clause.

        .. note::
           Entry wrappers remain visible to visitors and evaluators.
        """
        return (self.entry, *self.clauses)
