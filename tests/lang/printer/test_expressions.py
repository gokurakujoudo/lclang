"""Unit tests mirroring :mod:`pylcl.lang.printer.expressions`."""

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.lang.printer import to_source


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("1+2*3", "1 + 2 * 3"),
        ("(1+2)*3", "(1 + 2) * 3"),
        ("2**3**2", "2 ** 3 ** 2"),
        ("(2**3)**2", "(2 ** 3) ** 2"),
        ("-2**2", "-2 ** 2"),
        ("not a==b and c or d", "not a == b and c or d"),
        ("a??b??c", "a ?? b ?? c"),
        ("a if b else c if d else e", "a if b else c if d else e"),
        ("a < b is not c", "a < b is not c"),
    ],
)
def test_expression_precedence_is_canonical(source: str, canonical: str) -> None:
    """Minimal required parentheses preserve the parsed tree meaning."""
    printed = to_source(parse_expression(source))
    assert printed == canonical
    assert to_source(parse_expression(printed)) == canonical
