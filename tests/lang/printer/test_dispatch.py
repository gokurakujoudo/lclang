"""Integration tests mirroring :mod:`lclang.lang.engine.printer.source_printer`."""

from dataclasses import dataclass

import pytest

from lclang.error import LclValidationError
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.parser import parse_expression
from lclang.lang.engine.printer import to_source


def test_print_parse_print_is_idempotent() -> None:
    """A complex canonical rendering is stable across another parse."""
    source = "[function(x) if x > 0 else fallback for x in values if enabled]"
    first = to_source(parse_expression(source))
    second = to_source(parse_expression(first))
    assert first == second


def test_unknown_node_subclass_is_rejected() -> None:
    """Printer dispatch never hides an unsupported semantic node behind repr."""

    @dataclass(frozen=True, slots=True)
    class UnknownNode(LclAstNode):
        pass

    with pytest.raises(LclValidationError, match="unsupported AST node"):
        to_source(UnknownNode())
