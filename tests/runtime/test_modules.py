"""Unit tests mirroring :mod:`lclang.runtime.modules`."""

import pytest

from lclang.lang.parser import parse_expression
from lclang.types import ModuleName


def test_module_copies_definitions_into_read_only_snapshot() -> None:
    """Caller mutation cannot alter an established module."""
    from lclang.runtime import Module

    definitions = {"answer": parse_expression("42")}
    module = Module(ModuleName("app"), definitions)
    definitions["answer"] = parse_expression("0")
    assert module.definitions["answer"].value == 42  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        module.definitions["other"] = parse_expression("1")  # type: ignore[index]


@pytest.mark.parametrize(
    ("name", "definitions"),
    [
        (ModuleName(""), {"value": parse_expression("1")}),
        (ModuleName("app"), {"": parse_expression("1")}),
    ],
)
def test_module_rejects_empty_names(name: ModuleName, definitions: dict[str, object]) -> None:
    """Module and variable identifiers must be non-empty."""
    from typing import cast

    from lclang.ast import LclAstNode
    from lclang.runtime import Module

    with pytest.raises(ValueError):
        Module(name, cast(dict[str, LclAstNode], definitions))
