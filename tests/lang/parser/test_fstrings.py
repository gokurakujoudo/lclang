"""Unit tests mirroring :mod:`pylcl.lang.parser.fstrings`."""

import pytest

from pylcl.ast import (
    LclFormattedValue,
    LclJoinedString,
    LclName,
    LclStringText,
)
from pylcl.errors import LclSyntaxError
from pylcl.lang.parser import parse_expression
from pylcl.lang.printer import to_source
from pylcl.source import SourceOrigin
from pylcl.types import SourceName, VarName


def test_fstring_parts_become_semantic_ast_nodes() -> None:
    """Decoded text and parsed fields retain order and the outer source span."""
    origin = SourceOrigin(SourceName("template.lcl"))
    node = parse_expression("f'hello {name}!'", origin=origin)
    assert isinstance(node, LclJoinedString)
    assert node.span is not None
    assert node.span.origin is origin
    assert (node.span.start.offset, node.span.end.offset) == (0, 16)
    assert isinstance(node.values[0], LclStringText)
    assert node.values[0].text == "hello "
    assert isinstance(node.values[1], LclFormattedValue)
    expression = node.values[1].expression
    assert isinstance(expression, LclName)
    assert expression.identifier == VarName("name")
    assert isinstance(node.values[2], LclStringText)
    assert node.values[2].text == "!"


def test_fstring_modifiers_and_format_specs_convert_recursively() -> None:
    """Debug, conversion, and nested replacement fields become semantic data."""
    node = parse_expression("f'{value=!r:>{width}}'")
    assert isinstance(node, LclJoinedString)
    field = node.values[0]
    assert isinstance(field, LclFormattedValue)
    assert field.debug is True
    assert field.conversion == "r"
    assert field.format_spec is not None
    assert isinstance(field.format_spec.values[0], LclStringText)
    nested = field.format_spec.values[1]
    assert isinstance(nested, LclFormattedValue)
    assert isinstance(nested.expression, LclName)
    assert nested.expression.identifier == VarName("width")
    assert to_source(node) == 'f"{value=!r:>{width}}"'


def test_empty_fstring_becomes_empty_joined_string() -> None:
    """An interpolation with no parts still has a semantic root node."""
    node = parse_expression("f''")
    assert isinstance(node, LclJoinedString)
    assert node.values == ()


def test_invalid_embedded_expression_uses_outer_token_span() -> None:
    """Nested parser failures identify the complete interpolation token."""
    source = "f'{1 +}'"
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    error = caught.value
    assert error.code == "LCL1001"
    assert error.span is not None
    assert (error.span.start.offset, error.span.end.offset) == (0, len(source))
    assert isinstance(error.__cause__, LclSyntaxError)
