"""Behavioural tests for :mod:`lclang.lang.runtime.frame.binding_lookup`."""

import pytest

from lclang.error import LclValidationError
from lclang.lang import define_frame, define_module


def test_has_and_get_definition_follow_recursive_lookup_precedence() -> None:
    """Definitions, host values, masking, and missing names share one search."""
    ancestor = define_frame(
        define_module(
            "ancestor",
            {
                "inherited": "40",
                "masked": "1",
            },
        )
    )
    child = define_frame(
        define_module(
            "child",
            {
                "local": "inherited + 2",
                "same_frame": "7",
            },
        ),
        base=ancestor,
        preset={"masked": 5, "same_frame": 3, "host": 9},
    )

    assert child.has("local") is True
    assert child.has("inherited") is True
    assert child.has("host") is True
    assert child.has("missing") is False
    assert child.get_definition("local") is child.module.definitions["local"]
    assert child.get_definition("inherited") is ancestor.module.definitions["inherited"]
    assert child.get_definition("same_frame") is child.module.definitions["same_frame"]
    assert child.get_definition("masked") is None
    assert child.get_definition("host") is None
    assert child.get_definition("missing") is None


def test_lookup_inspection_does_not_evaluate_or_cache_a_definition() -> None:
    """Inspection returns syntax and presence without executing host code."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return 42

    frame = define_frame(
        define_module("app", {"answer": "produce()"}),
        preset={"produce": produce},
    )

    assert frame.has("answer") is True
    assert frame.get_definition("answer") is frame.module.definitions["answer"]
    assert calls == 0


@pytest.mark.parametrize("method", ["has", "get_definition"])
def test_lookup_inspection_rejects_empty_names(method: str) -> None:
    """Inspection uses the same non-empty-name contract as get."""
    frame = define_frame()
    with pytest.raises(LclValidationError, match="variable name cannot be empty"):
        getattr(frame, method)("")
