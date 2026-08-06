"""Unit tests mirroring :mod:`pylcl.ast.comprehensions`."""

import pytest

from pylcl.ast import LclConstant, LclDictUnpack, LclKeyValue, LclName
from pylcl.ast.comprehensions import (
    LclComprehensionClause,
    LclDictComprehension,
    LclGenerator,
    LclListComprehension,
    LclSetComprehension,
)
from pylcl.types import VarName


def clause() -> LclComprehensionClause:
    """Build one reusable immutable clause for structural assertions."""
    target = LclName(identifier=VarName("item"))
    iterable = LclName(identifier=VarName("items"))
    condition = LclName(identifier=VarName("enabled"))
    return LclComprehensionClause(target, iterable, (condition,))


def test_clause_children_are_target_iterable_then_filters() -> None:
    """Dependency traversal retains the complete clause source order."""
    node = clause()
    assert node.children() == (node.target, node.iterable, *node.conditions)


def test_comprehension_heads_precede_clauses() -> None:
    """All collection forms expose their head then ordered clauses."""
    head = LclConstant(value=1)
    item_clause = clause()
    pair = LclKeyValue(head, head)
    unpack = LclDictUnpack(head)
    assert LclGenerator(head, (item_clause,)).children() == (head, item_clause)
    assert LclListComprehension(head, (item_clause,)).children() == (head, item_clause)
    assert LclSetComprehension(head, (item_clause,)).children() == (head, item_clause)
    assert LclDictComprehension(pair, (item_clause,)).children() == (pair, item_clause)
    assert LclDictComprehension(unpack, (item_clause,)).entry is unpack


@pytest.mark.parametrize(
    "node_type",
    [LclGenerator, LclListComprehension, LclSetComprehension],
)
def test_sequence_comprehensions_require_a_clause(node_type: type[object]) -> None:
    """A comprehension node cannot silently behave like a display."""
    with pytest.raises(ValueError):
        node_type(LclConstant(value=1), ())  # type: ignore[call-arg]


def test_dict_comprehension_requires_a_clause() -> None:
    """Dictionary comprehension cardinality is enforced equally."""
    with pytest.raises(ValueError):
        LclDictComprehension(LclDictUnpack(LclConstant(value={})), ())
