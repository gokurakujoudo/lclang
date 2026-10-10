"""Immutable AST values for ordinary operator expressions."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast.base import LclAstNode
from lclang.ast.operators import (
    BinaryOperator,
    BooleanOperator,
    ComparisonOperator,
    UnaryOperator,
)
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.core import Code as core_codes


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclUnary(LclAstNode):
    """Represent one unary operation.

    :param operator: Unary operator spelling.
    :param operand: Expression receiving the operation.

    .. note::
       The inherited source span is keyword-only.
    """

    operator: UnaryOperator
    operand: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the single operand.

        :returns: A one-element operand tuple.

        .. note::
           The operator enum is scalar metadata.
        """
        return (self.operand,)


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclBinary(LclAstNode):
    """Represent one binary operation.

    :param left: Left operand.
    :param operator: Binary operator spelling.
    :param right: Right operand.

    .. note::
       Associativity is preserved by nested binary nodes.
    """

    left: LclAstNode
    operator: BinaryOperator
    right: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return left then right operand.

        :returns: Both operands in source order.

        .. note::
           No operator node is inserted between operands.
        """
        return (self.left, self.right)


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclBoolean(LclAstNode):
    """Represent a flattened short-circuit Boolean operation.

    :param operator: Shared ``and`` or ``or`` operator.
    :param values: At least two operands in source order.
    :raises LclValidationError: If fewer than two operands are supplied.

    .. note::
       Flattening applies only to adjacent identical Boolean operators.
    """

    operator: BooleanOperator
    values: tuple[LclAstNode, ...]

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def __post_init__(self) -> None:
        """Enforce Boolean expression cardinality.

        :raises LclValidationError: If fewer than two operands are supplied.
        """
        if len(self.values) < 2:
            raise LclValidationError(
                "Boolean expression requires at least two operands",
                code=core_codes.E27_BOOLEAN_EXPRESSION_REQUIRES_AT_LEAST_TWO_OPERANDS,
            )

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return all Boolean operands.

        :returns: Operands in source order.

        .. note::
           Runtime evaluation may stop before visiting every child.
        """
        return self.values


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclCompare(LclAstNode):
    """Represent one comparison chain.

    :param left: First comparison operand.
    :param operators: One operator per comparator.
    :param comparators: Non-empty right-hand operand sequence.
    :raises LclValidationError: If operators and comparators differ or are empty.

    .. note::
       Chained middle operands are evaluated once by the interpreter.
    """

    left: LclAstNode
    operators: tuple[ComparisonOperator, ...]
    comparators: tuple[LclAstNode, ...]

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def __post_init__(self) -> None:
        """Enforce comparison-chain cardinality.

        :raises LclValidationError: If operators and comparators are empty or mismatched.
        """
        if not self.operators or len(self.operators) != len(self.comparators):
            raise LclValidationError(
                "comparison requires one comparator per operator",
                code=core_codes.E27_COMPARISON_REQUIRES_ONE_COMPARATOR_PER_OPERATOR,
            )

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the left value followed by comparators.

        :returns: All comparison operands in source order.

        .. note::
           Operator enums do not appear in AST traversal.
        """
        return (self.left, *self.comparators)


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclConditional(LclAstNode):
    """Represent ``when_true if condition else when_false``.

    :param when_true: Value selected for a truthy condition.
    :param condition: Expression controlling branch selection.
    :param when_false: Value selected for a false condition.

    .. note::
       Children follow source order, not runtime evaluation order.
    """

    when_true: LclAstNode
    condition: LclAstNode
    when_false: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the three source-order expressions.

        :returns: True value, condition, then false value.

        .. note::
           Only one value branch is evaluated at runtime.
        """
        return (self.when_true, self.condition, self.when_false)


@guard_constructor(LclValidationError, core_codes.NATIVE_827)
@dataclass(frozen=True, slots=True)
class LclCoalesce(LclAstNode):
    """Represent null-coalescing ``left ?? right``.

    :param left: Preferred value.
    :param right: Fallback evaluated only for a null left value.

    .. note::
       False and zero do not select the fallback.
    """

    left: LclAstNode
    right: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_827)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return preferred then fallback expression.

        :returns: Both operands in source order.

        .. note::
           Runtime evaluation may skip the right child.
        """
        return (self.left, self.right)
