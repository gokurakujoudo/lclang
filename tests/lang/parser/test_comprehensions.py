"""Unit tests mirroring :mod:`lclang.lang.parser.comprehensions`."""

import pytest

from lclang.ast import LclConstant, LclDictUnpack, LclKeyValue, LclName, LclStarred
from lclang.ast.comprehensions import (
    LclDictComprehension,
    LclGenerator,
    LclListComprehension,
    LclSetComprehension,
)
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind, scan_tokens
from lclang.lang.parser import parse_expression
from lclang.lang.parser.comprehensions import (
    ComprehensionKind,
    parse_comprehension,
)
from lclang.lang.parser.stream import TokenStream
from lclang.types import VarName


def test_generator_and_collection_comprehension_forms() -> None:
    """Each delimiter maps to its dedicated semantic node type."""
    generator = parse_expression("(item for item in items)")
    listed = parse_expression("[item for item in items]")
    set_node = parse_expression("{item for item in items}")
    mapping = parse_expression("{item: value for item in items}")
    assert isinstance(generator, LclGenerator)
    assert isinstance(listed, LclListComprehension)
    assert isinstance(set_node, LclSetComprehension)
    assert isinstance(mapping, LclDictComprehension)
    assert isinstance(mapping.entry, LclKeyValue)


def test_multiple_clauses_and_filters_preserve_order() -> None:
    """Repeated for and if components remain attached to their owning clause."""
    node = parse_expression(
        "[pair for left in lefts if left for right in rights if right if enabled]"
    )
    assert isinstance(node, LclListComprehension)
    assert len(node.clauses) == 2
    assert node.clauses[0].target.identifier == VarName("left")
    assert len(node.clauses[0].conditions) == 1
    assert node.clauses[1].target.identifier == VarName("right")
    assert len(node.clauses[1].conditions) == 2


def test_pep798_unpacking_heads_are_explicit() -> None:
    """Iterable and mapping unpack comprehensions preserve wrapper nodes."""
    listed = parse_expression("[*group for group in groups]")
    set_node = parse_expression("{*group for group in groups}")
    mapping = parse_expression("{**mapping for mapping in mappings}")
    assert isinstance(listed, LclListComprehension)
    assert isinstance(listed.element, LclStarred)
    assert isinstance(set_node, LclSetComprehension)
    assert isinstance(set_node.element, LclStarred)
    assert isinstance(mapping, LclDictComprehension)
    assert isinstance(mapping.entry, LclDictUnpack)


def test_grouped_conditional_is_valid_inside_clause_expression() -> None:
    """Parentheses explicitly disambiguate conditional iterable or filter values."""
    node = parse_expression("[item for item in (yes if flag else no) if (a if b else c)]")
    assert isinstance(node, LclListComprehension)
    assert len(node.clauses[0].conditions) == 1


@pytest.mark.parametrize(
    "source",
    [
        "[item for in items]",
        "[item for item items]",
        "[item for item in]",
        "[item for item in items if]",
        "[item for item in items, other]",
        "{item: value for item in items, other: value}",
        "[*item for 1 in items]",
        "(item for item in items",
    ],
)
def test_invalid_comprehension_reports_syntax_error(source: str) -> None:
    """Incomplete clauses, invalid targets, and trailing entries are rejected."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None


def test_double_underscore_comprehension_binding_is_rejected() -> None:
    """Reserved double-underscore names cannot become comprehension targets."""
    with pytest.raises(LclSyntaxError, match="double underscore"):
        parse_expression("[item for __item in items]")


def test_dictionary_comprehension_helper_rejects_non_entry_head() -> None:
    """Direct parser-helper use cannot construct a dictionary from a sequence head."""
    stream = TokenStream(scan_tokens("for item in items}"))
    head = LclConstant(value=1)

    def parse_name() -> LclName:
        """Consume and return the simple iterable name used by this focused fixture."""
        token = stream.expect(TokenKind.IDENTIFIER, "expected fixture name")
        return LclName(VarName(token.lexeme), span=token.span)

    with pytest.raises(LclSyntaxError, match="invalid dictionary comprehension head") as caught:
        parse_comprehension(
            stream,
            head,
            ComprehensionKind.DICT,
            stream.current.span,
            parse_name,
        )
    assert caught.value.span == head.span
