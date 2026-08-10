"""Unit tests mirroring :mod:`lclang.lang.evaluator.function_arguments`."""

import pytest

from lclang.ast import ParameterKind
from lclang.lang.evaluator.function_arguments import (
    MISSING_PARAMETER,
    BoundParameter,
    bind_arguments,
)


def test_argument_binding_handles_every_parameter_kind_without_mutating_input() -> None:
    """Composite binding preserves caller input and normalizes every parameter family."""
    parameters = (
        BoundParameter("first", ParameterKind.POSITIONAL),
        BoundParameter("second", ParameterKind.POSITIONAL, 2),
        BoundParameter("items", ParameterKind.VAR_POSITIONAL),
        BoundParameter("option", ParameterKind.KEYWORD_ONLY, 3),
        BoundParameter("extras", ParameterKind.VAR_KEYWORD),
    )
    named: dict[str, object] = {"option": 4, "named": 5}
    assert bind_arguments(parameters, (1, 6, 7), named) == {
        "first": 1,
        "second": 6,
        "items": (7,),
        "option": 4,
        "extras": {"named": 5},
    }
    assert named == {"option": 4, "named": 5}


@pytest.mark.parametrize(
    ("parameters", "args", "kwargs", "message"),
    [
        ((BoundParameter("item", ParameterKind.POSITIONAL),), (), {}, "missing"),
        (
            (BoundParameter("item", ParameterKind.POSITIONAL),),
            (1,),
            {"item": 2},
            "multiple",
        ),
        ((BoundParameter("item", ParameterKind.POSITIONAL),), (1, 2), {}, "too many"),
        ((), (), {"item": 1}, "unexpected"),
    ],
)
def test_argument_binding_rejects_invalid_call_shapes(
    parameters: tuple[BoundParameter, ...],
    args: tuple[object, ...],
    kwargs: dict[str, object],
    message: str,
) -> None:
    """Rainy call shapes retain deterministic native TypeError diagnostics."""
    with pytest.raises(TypeError, match=message):
        bind_arguments(parameters, args, kwargs)


def test_bound_parameter_uses_a_distinct_missing_default_sentinel() -> None:
    """An omitted default remains distinguishable from explicit ``None``."""
    required = BoundParameter("item", ParameterKind.POSITIONAL)
    optional = BoundParameter("item", ParameterKind.POSITIONAL, None)
    assert required.default is MISSING_PARAMETER
    assert optional.default is None
