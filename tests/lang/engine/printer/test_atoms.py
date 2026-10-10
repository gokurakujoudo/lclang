"""Unit tests mirroring :mod:`lclang.lang.engine.printer.atom_rendering`."""

import pytest

from lclang.common.identifiers import VarName
from lclang.error import LclValidationError
from lclang.lang.ast import (
    LclConstant,
    LclFormattedValue,
    LclJoinedString,
    LclName,
    LclStringText,
)
from lclang.lang.engine.parser import parse_expression
from lclang.lang.engine.printer import to_source


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("None", "None"),
        ("True", "True"),
        ("False", "False"),
        ("1_000", "1000"),
        ("1.50", "1.5"),
        (r"'a\n'", r"'a\n'"),
        (r"b'a\x42'", "b'aB'"),
        ("name", "name"),
    ],
)
def test_atom_canonical_source(source: str, canonical: str) -> None:
    """Decoded constants and names use one deterministic spelling."""
    assert to_source(parse_expression(source)) == canonical


def test_semantic_fstring_has_canonical_escaping_and_fields() -> None:
    """Text, debug, conversion, and recursive format specs remain explicit."""
    spec = LclJoinedString(values=(LclStringText(text="04"),))
    field = LclFormattedValue(
        expression=LclName(identifier=VarName("value")),
        conversion="r",
        format_spec=spec,
        debug=True,
    )
    node = LclJoinedString(values=(LclStringText(text='a\\"{}\n\r\t'), field))
    assert to_source(node) == 'f"a\\\\\\"{{}}\\n\\r\\t{value=!r:04}"'
    assert to_source(LclJoinedString()) == 'f""'


def test_unsupported_constant_value_is_rejected() -> None:
    """Constants outside the language value set never fall back to repr."""
    with pytest.raises(LclValidationError, match="unsupported constant value"):
        to_source(LclConstant(value=object()))


def test_unsupported_joined_string_child_is_rejected() -> None:
    """Joined strings accept only semantic text and field wrappers."""
    node = LclJoinedString(values=(LclConstant(value=1),))
    with pytest.raises(LclValidationError, match="unsupported value"):
        to_source(node)
