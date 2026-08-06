"""Acceptance tests for the stable package-root language API."""

import pylcl
from pylcl.ast import LclConstant
from pylcl.lang import parse_expression, to_source


def test_root_exports_language_front_end_services() -> None:
    """Callers can parse and print without importing implementation packages."""
    assert pylcl.parse_expression is parse_expression
    assert pylcl.to_source is to_source
    node = pylcl.parse_expression("1 + 2")
    assert pylcl.to_source(node) == "1 + 2"


def test_ast_families_remain_namespaced() -> None:
    """Root exports stay small while AST construction remains available."""
    assert isinstance(pylcl.parse_expression("1"), LclConstant)
    assert "parse_expression" in pylcl.__all__
    assert "to_source" in pylcl.__all__
