"""Deterministic AST round-trip properties and bounded parser fuzzing."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

import lclang
from lclang.ast import LclAstNode
from lclang.errors import LclSyntaxError
from tests.support.property_strategies import AST_VALUES, ast_shape


@given(AST_VALUES)
def test_generated_ast_round_trip_preserves_shape_value_and_canonical_source(
    node: LclAstNode,
) -> None:
    """Generated safe ASTs remain structurally and semantically canonical."""
    source = lclang.to_source(node)
    parsed = lclang.parse_expression(source)
    assert ast_shape(parsed) == ast_shape(node)
    assert lclang.to_source(parsed) == source
    assert lclang.evaluate_sync(parsed) == lclang.evaluate_sync(node)
    for descendant in parsed.walk():
        assert 0 <= descendant.span.start.offset <= descendant.span.end.offset <= len(source)


@settings(max_examples=500)
@given(st.text(max_size=128))
def test_bounded_unicode_input_returns_ast_or_structured_syntax_error(source: str) -> None:
    """Arbitrary bounded text never leaks parser implementation failures."""
    try:
        expression = lclang.parse_expression(source)
    except LclSyntaxError:
        return
    canonical = lclang.to_source(expression)
    assert lclang.to_source(lclang.parse_expression(canonical)) == canonical


def test_recorded_delimiter_operator_and_unicode_regressions() -> None:
    """Explicit rainy fragments remain structured after fuzz minimization."""
    fragments = (
        "(",
        "[1,",
        "{**}",
        "1 +",
        "f'{value'",
        "²",
        "\ud800",
        "\x00",
        "not in",
    )
    for source in fragments:
        try:
            lclang.parse_expression(source)
        except LclSyntaxError:
            continue
        raise AssertionError(f"malformed source parsed unexpectedly: {source!r}")
