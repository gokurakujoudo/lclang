"""Acceptance tests for the stable package-root language API."""

import lclang
from lclang.ast import LclConstant
from lclang.lang import parse_expression, to_source


def test_root_exports_language_front_end_services() -> None:
    """Callers can parse and print without importing implementation packages."""
    assert lclang.parse_expression is parse_expression
    assert lclang.to_source is to_source
    node = lclang.parse_expression("1 + 2")
    assert lclang.to_source(node) == "1 + 2"


def test_ast_families_remain_namespaced() -> None:
    """Root exports stay small while AST construction remains available."""
    assert isinstance(lclang.parse_expression("1"), LclConstant)
    assert "parse_expression" in lclang.__all__
    assert "to_source" in lclang.__all__


def test_root_exports_record_result_type() -> None:
    """Evaluated records have one stable package-root Python type."""
    value = lclang.evaluate_sync("{answer=42}")
    assert isinstance(value, lclang.LclRecord)
    assert lclang.__all__.count("LclRecord") == 1
