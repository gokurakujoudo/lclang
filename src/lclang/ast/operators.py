"""Stable source spellings for LCL expression operators."""

from enum import StrEnum


class UnaryOperator(StrEnum):
    """Identify unary operators without evaluator behaviour.

    .. note::
       Values are exact canonical source spellings.
    """

    # Unitless operator spellings come from the language grammar; exact tokens preserve parsing
    # and canonical printing.
    POSITIVE = "+"
    NEGATIVE = "-"
    INVERT = "~"
    NOT = "not"


class BinaryOperator(StrEnum):
    """Identify arithmetic and bitwise binary operators.

    .. note::
       Precedence is owned by the parser rather than this enum.
    """

    # Unitless operator spellings come from the language grammar; exact tokens preserve parsing
    # and canonical printing.
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

    # Unitless operator spellings come from the language grammar; exact tokens preserve parsing
    # and canonical printing.
    AND = "and"
    OR = "or"


class ComparisonOperator(StrEnum):
    """Identify ordered, membership, and identity comparisons.

    .. note::
       Two-word values are emitted and printed as one logical operator.
    """

    # Unitless operator spellings come from the language grammar; exact tokens preserve parsing
    # and canonical printing.
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
