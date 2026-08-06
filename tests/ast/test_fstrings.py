"""Unit tests mirroring :mod:`pylcl.ast.fstrings`."""

import pytest

from pylcl.ast import LclConstant
from pylcl.ast.fstrings import LclFormattedValue, LclJoinedString, LclStringText


def test_joined_string_children_preserve_part_order() -> None:
    """Semantic f-string parts participate in ordinary AST traversal."""
    expression = LclConstant(value=42)
    formatted = LclFormattedValue(expression=expression, conversion="r")
    text = LclStringText(text="answer=")
    joined = LclJoinedString(values=(text, formatted))
    assert joined.children() == (text, formatted)
    assert tuple(joined.walk()) == (joined, text, formatted, expression)


def test_formatted_value_exposes_optional_format_spec() -> None:
    """Expression then format spec is the stable visitor child order."""
    expression = LclConstant(value=1)
    spec = LclJoinedString(values=(LclStringText(text="04d"),))
    node = LclFormattedValue(expression=expression, format_spec=spec, debug=True)
    assert node.children() == (expression, spec)


@pytest.mark.parametrize("conversion", ["x", "", "rr"])
def test_formatted_value_rejects_unknown_conversion(conversion: str) -> None:
    """Only the explicit V1 conversion set enters the semantic AST."""
    with pytest.raises(ValueError):
        LclFormattedValue(expression=LclConstant(value=1), conversion=conversion)


def test_string_text_requires_text_value() -> None:
    """Text parts reject empty values that add no semantic information."""
    with pytest.raises(ValueError):
        LclStringText(text="")
