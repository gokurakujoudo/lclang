"""Unit tests mirroring :mod:`pylcl.lang.printer.collections`."""

import pytest

from pylcl.ast import LclConstant, LclDict
from pylcl.lang.parser import parse_expression
from pylcl.lang.printer import to_source


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("()", "()"),
        ("(1,)", "(1,)"),
        ("[1,*items]", "[1, *items]"),
        ("{1,*items}", "{1, *items}"),
        ("{'a':1,**other}", "{'a': 1, **other}"),
        ("(x for x in xs if x)", "(x for x in xs if x)"),
        ("[*x for x in xs]", "[*x for x in xs]"),
        ("{x for x in xs}", "{x for x in xs}"),
        ("{x:y for x in xs}", "{x: y for x in xs}"),
        ("{**x for x in xs}", "{**x for x in xs}"),
    ],
)
def test_collection_source_is_canonical(source: str, canonical: str) -> None:
    """Displays, unpacking, and comprehensions use stable delimiters and spaces."""
    assert to_source(parse_expression(source)) == canonical


def test_unsupported_dictionary_entry_is_rejected() -> None:
    """A malformed dictionary tree fails at its entry ownership boundary."""
    node = LclDict(entries=(LclConstant(value=1),))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unsupported entry"):
        to_source(node)
