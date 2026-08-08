"""Unit tests mirroring :mod:`pylcl.lang.parser.control_forms`."""

import pytest

from pylcl.ast import LclAssert
from pylcl.ast.control_forms import LclTry, LclWith
from pylcl.errors import LclSyntaxError
from pylcl.lang.parser import parse_expression
from pylcl.types import VarName


def test_try_handlers_bind_names_and_preserve_finally() -> None:
    """Typed, bare, repeated, and finalizer clauses build ordered nodes."""
    node = parse_expression(
        "try: operation() "
        "except FirstError as first: recover(first) "
        "except SecondError: recover() "
        "except: fallback() "
        "finally: cleanup()"
    )
    assert isinstance(node, LclTry)
    assert len(node.handlers) == 3
    assert node.handlers[0].name == VarName("first")
    assert node.handlers[0].exception is not None
    assert node.handlers[1].name is None
    assert node.handlers[2].exception is None
    assert node.finally_body is not None


def test_try_may_have_only_finally() -> None:
    """Finalization without recovery is a valid control expression."""
    node = parse_expression("try: operation() finally: cleanup()")
    assert isinstance(node, LclTry)
    assert node.handlers == ()
    assert node.finally_body is not None


def test_with_items_preserve_optional_targets_and_body() -> None:
    """Multiple context items retain left-to-right source ordering."""
    node = parse_expression("with open_file() as file, lock(): assert(file)")
    assert isinstance(node, LclWith)
    assert len(node.items) == 2
    assert node.items[0].target == VarName("file")
    assert node.items[1].target is None
    assert isinstance(node.body, LclAssert)


def test_grouped_control_form_is_valid_nested_expression() -> None:
    """Grouping permits a control form where an ordinary atom is expected."""
    node = parse_expression("[(with lock(): value)]")
    assert node.children()
    assert isinstance(node.children()[0], LclWith)


@pytest.mark.parametrize(
    "source",
    [
        "try: value",
        "try value except: fallback",
        "try: value except Error as: fallback",
        "try: value except: fallback except Error: other",
        "try: value finally cleanup",
        "with: value",
        "with resource as: value",
        "with resource value",
        "with resource,: value",
    ],
)
def test_invalid_control_form_reports_syntax_error(source: str) -> None:
    """Missing clauses, targets, colons, and invalid ordering are rejected."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None


@pytest.mark.parametrize(
    "source",
    [
        "try: value except Error as __error: fallback",
        "with resource as __resource: value",
    ],
)
def test_double_underscore_control_bindings_are_rejected(source: str) -> None:
    """Exception and context aliases share the reserved binding rule."""
    with pytest.raises(LclSyntaxError, match="double underscore"):
        parse_expression(source)
