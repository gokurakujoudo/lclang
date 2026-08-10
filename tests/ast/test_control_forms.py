"""Unit tests mirroring :mod:`lclang.ast.control_forms`."""

import pytest

from lclang.ast import LclConstant
from lclang.ast.control_forms import LclExceptHandler, LclTry, LclWith, LclWithItem
from lclang.types import VarName


def test_control_form_children_preserve_source_order() -> None:
    """Contexts, handlers, bodies, and finalizers remain structurally explicit."""
    value = LclConstant(value=1)
    context = LclWithItem(value, VarName("resource"))
    handler = LclExceptHandler(value, VarName("error"), value)
    with_node = LclWith((context,), value)
    try_node = LclTry(value, (handler,), value)
    assert context.children() == (value,)
    assert handler.children() == (value, value)
    assert with_node.children() == (context, value)
    assert try_node.children() == (value, handler, value)


def test_bare_handler_has_only_body_child() -> None:
    """The absence of an exception matcher and binding remains explicit."""
    body = LclConstant(value=None)
    handler = LclExceptHandler(None, None, body)
    assert handler.children() == (body,)
    assert LclTry(body, (handler,)).children() == (body, handler)


def test_try_requires_handler_or_finally() -> None:
    """A try node cannot silently behave as a grouping wrapper."""
    with pytest.raises(ValueError):
        LclTry(LclConstant(value=1), (), None)


def test_with_requires_item_and_nonempty_target() -> None:
    """Context forms require one manager and usable optional target names."""
    value = LclConstant(value=1)
    with pytest.raises(ValueError):
        LclWith((), value)
    with pytest.raises(ValueError):
        LclWithItem(value, VarName(""))


def test_except_handler_rejects_empty_and_bare_bindings() -> None:
    """Exception bindings must be non-empty and require a typed matcher."""
    value = LclConstant(value=1)
    with pytest.raises(ValueError, match="cannot be empty"):
        LclExceptHandler(value, VarName(""), value)
    with pytest.raises(ValueError, match="bare except"):
        LclExceptHandler(None, VarName("error"), value)
