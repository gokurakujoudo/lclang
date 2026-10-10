"""Behavioural tests for CLI validation helpers."""

import pytest

from lclang.cli.declaration_validation import freeze_mapping, is_lcl_identifier, normalize_text
from lclang.error import LclValidationError


def test_text_identifier_and_mapping_validation() -> None:
    """Helpers normalize valid input and detach caller mappings."""
    assert normalize_text("  hello\n world ", "summary") == "hello world"
    assert is_lcl_identifier("配置") is True
    assert is_lcl_identifier("bad-key") is False
    assert is_lcl_identifier("value +") is False
    assert is_lcl_identifier(1) is False
    source = {"x": 1}
    frozen = freeze_mapping(source, "values")
    source["x"] = 2
    assert frozen == {"x": 1}
    with pytest.raises(LclValidationError, match="summary"):
        normalize_text(1, "summary")  # type: ignore[arg-type]
    with pytest.raises(LclValidationError, match="mapping"):
        freeze_mapping(1, "values")  # type: ignore[arg-type]
    with pytest.raises(LclValidationError, match="names"):
        freeze_mapping({1: "x"}, "values")  # type: ignore[dict-item]
