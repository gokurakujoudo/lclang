"""Bounded custom-AST strategies and span-independent normalization."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from lclang.ast import LclAstNode, LclBinary, LclConstant, LclTuple, LclUnary
from lclang.ast.operators import BinaryOperator, UnaryOperator

NUMERIC_LEAVES: SearchStrategy[LclAstNode] = st.builds(
    LclConstant,
    st.integers(min_value=0, max_value=20),
)
NUMERIC_VALUES: SearchStrategy[LclAstNode] = st.recursive(
    NUMERIC_LEAVES,
    lambda children: st.one_of(
        st.builds(
            LclUnary,
            st.sampled_from((UnaryOperator.POSITIVE, UnaryOperator.NEGATIVE, UnaryOperator.INVERT)),
            children,
        ),
        st.builds(
            LclBinary,
            children,
            st.sampled_from((BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY)),
            children,
        ),
    ),
    max_leaves=20,
)
AST_VALUES: SearchStrategy[LclAstNode] = st.one_of(
    NUMERIC_VALUES,
    st.builds(LclTuple, st.lists(NUMERIC_VALUES, max_size=4).map(tuple)),
)


def ast_shape(value: object) -> object:
    """Return a recursively normalized value excluding source spans.

    :param value: AST node or nested scalar metadata.
    :returns: Hashable-style structural data suitable for equality assertions.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return tuple(ast_shape(item) for item in value)
    if isinstance(value, LclAstNode) and is_dataclass(value):
        members = tuple(
            (field.name, ast_shape(getattr(value, field.name)))
            for field in fields(value)
            if field.name != "span"
        )
        return type(value).__name__, members
    return value
