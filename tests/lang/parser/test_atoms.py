"""Unit tests mirroring :mod:`lclang.lang.parser.atoms`."""

import pytest

from lclang.ast import LclConstant, LclName
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import scan_tokens
from lclang.lang.parser.atoms import parse_atom
from lclang.lang.parser.stream import TokenStream
from lclang.types import VarName


def atom(source: str) -> LclConstant | LclName:
    """Parse one standalone atom for focused unit assertions."""
    stream = TokenStream(scan_tokens(source))
    node = parse_atom(stream, lambda: parse_atom(stream, lambda: node))
    assert isinstance(node, (LclConstant, LclName))
    return node


@pytest.mark.parametrize(
    ("source", "value"),
    [("1", 1), ("1.5", 1.5), ("True", True), ("False", False), ("None", None)],
)
def test_literal_atoms_preserve_decoded_values(source: str, value: object) -> None:
    """Decoded lexer values pass into constants without reparsing source."""
    parsed = atom(source)
    assert isinstance(parsed, LclConstant)
    assert parsed.value == value
    assert parsed.span.start.offset == 0
    assert parsed.span.end.offset == len(source)


def test_name_atom_uses_typed_identifier() -> None:
    """Identifier lexemes become explicit variable-name values."""
    assert atom("answer") == LclName(identifier=VarName("answer"), span=atom("answer").span)


@pytest.mark.parametrize(
    ("source", "value"),
    [("'a' 'b'", "ab"), ("b'a' b'b'", b"ab")],
)
def test_adjacent_same_kind_literals_concatenate(source: str, value: object) -> None:
    """Adjacent plain literals become one constant with a combined span."""
    parsed = atom(source)
    assert isinstance(parsed, LclConstant)
    assert parsed.value == value
    assert parsed.span.end.offset == len(source)


@pytest.mark.parametrize("source", ["'a' b'b'", ""])
def test_reserved_or_invalid_atom_reports_syntax_error(source: str) -> None:
    """Mixed literal domains and absent atoms fail at the atom boundary."""
    stream = TokenStream(scan_tokens(source))
    with pytest.raises(LclSyntaxError):
        parse_atom(stream, lambda: LclConstant(value=None))


def test_frame_proxy_is_a_standalone_special_constant() -> None:
    """The proxy marker parses as a constant and cannot be nested."""
    import lclang
    from lclang.lang.parser import parse_expression
    from lclang.lang.printer import to_source

    node = parse_expression("FRAME_PROXY")
    assert isinstance(node, LclConstant)
    assert node.value is lclang.FRAME_PROXY
    assert repr(lclang.FRAME_PROXY) == "FRAME_PROXY"
    assert to_source(node) == "FRAME_PROXY"
    with pytest.raises(LclSyntaxError, match="complete expression"):
        parse_expression("[FRAME_PROXY]")
