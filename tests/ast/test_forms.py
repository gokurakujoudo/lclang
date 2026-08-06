"""Unit tests mirroring :mod:`pylcl.ast.forms`."""

import pytest

from pylcl.ast import LclConstant
from pylcl.ast.forms import (
    LclAssert,
    LclFunction,
    LclParameter,
    LclRaise,
    ParameterKind,
)
from pylcl.types import VarName


def test_parameter_and_form_children_are_deterministic() -> None:
    """Defaults, parameters, bodies, values, and messages retain source order."""
    default = LclConstant(value=1)
    parameter = LclParameter(VarName("value"), ParameterKind.POSITIONAL, default)
    body = LclConstant(value=2)
    function = LclFunction((parameter,), body)
    raised = LclRaise(body)
    asserted = LclAssert(default, body)
    assert parameter.children() == (default,)
    assert function.children() == (parameter, body)
    assert raised.children() == (body,)
    assert asserted.children() == (default, body)
    assert LclAssert(default).children() == (default,)


@pytest.mark.parametrize("kind", [ParameterKind.VAR_POSITIONAL, ParameterKind.VAR_KEYWORD])
def test_variadic_parameter_rejects_default(kind: ParameterKind) -> None:
    """Variadic capture and default-value semantics cannot be combined."""
    with pytest.raises(ValueError):
        LclParameter(VarName("items"), kind, LclConstant(value=1))


def test_parameter_rejects_empty_name() -> None:
    """Every binding parameter must have a usable name."""
    with pytest.raises(ValueError):
        LclParameter(VarName(""), ParameterKind.POSITIONAL)
