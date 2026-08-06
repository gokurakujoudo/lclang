"""Unit tests mirroring :mod:`pylcl.lang.printer.primaries`."""

import pytest

from pylcl.ast import LclCall, LclConstant, LclName, LclSlice
from pylcl.lang.parser import parse_expression
from pylcl.lang.printer import to_source
from pylcl.types import VarName


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("root.child?.leaf", "root.child?.leaf"),
        ("items[1:stop:2]", "items[1:stop:2]"),
        ("items[:stop:]", "items[:stop]"),
        ("items[1]", "items[1]"),
        ("items[1,2]", "items[1, 2]"),
        (
            "function(1,*items,key=2,**options)",
            "function(1, *items, key=2, **options)",
        ),
    ],
)
def test_primary_source_is_canonical(source: str, canonical: str) -> None:
    """Chained primaries and argument wrappers retain exact structural meaning."""
    assert to_source(parse_expression(source)) == canonical


def test_standalone_slice_renders_omitted_bounds() -> None:
    """A semantic slice node has a deterministic source fragment."""
    node = LclSlice(lower=None, upper=LclConstant(value=2), step=None)
    assert to_source(node) == ":2"


def test_unsupported_call_argument_is_rejected() -> None:
    """A malformed call tree fails at its argument ownership boundary."""
    node = LclCall(
        function=LclName(identifier=VarName("function")),
        arguments=(LclConstant(value=1),),  # type: ignore[arg-type]
    )
    with pytest.raises(TypeError, match="unsupported argument"):
        to_source(node)
