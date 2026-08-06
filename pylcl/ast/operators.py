"""Stable source spellings for LCL expression operators."""

from enum import StrEnum


class UnaryOperator(StrEnum):
    """Identify unary operators without evaluator behaviour.

    .. note::
       Values are exact canonical source spellings.
    """

    POSITIVE = "+"
    NEGATIVE = "-"
    INVERT = "~"
    NOT = "not"


class BinaryOperator(StrEnum):
    """Identify arithmetic and bitwise binary operators.

    .. note::
       Precedence is owned by the parser rather than this enum.
    """

    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    MATRIX_MULTIPLY = "@"
    TRUE_DIVIDE = "/"
    FLOOR_DIVIDE = "//"
    MODULO = "%"
    POWER = "**"
    LEFT_SHIFT = "<<"
    RIGHT_SHIFT = ">>"
    BIT_AND = "&"
    BIT_XOR = "^"
    BIT_OR = "|"


class BooleanOperator(StrEnum):
    """Identify short-circuit Boolean operators.

    .. note::
       Nodes may contain more than two operands for canonical flattening.
    """

    AND = "and"
    OR = "or"


class ComparisonOperator(StrEnum):
    """Identify ordered, membership, and identity comparisons.

    .. note::
       Two-word values are emitted and printed as one logical operator.
    """

    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="
    EQUAL = "=="
    NOT_EQUAL = "!="
    IN = "in"
    NOT_IN = "not in"
    IS = "is"
    IS_NOT = "is not"
