"""Unit tests mirroring :mod:`pylcl.lang.parser.forms`."""

import pytest

from pylcl.ast import LclBinary, LclCall, LclList
from pylcl.ast.forms import LclAssert, LclFunction, LclRaise, ParameterKind
from pylcl.errors import LclSyntaxError
from pylcl.lang.parser import parse_expression
from pylcl.types import VarName


def test_function_parameters_preserve_kind_default_and_body() -> None:
    """All parameter categories become ordered explicit AST values."""
    node = parse_expression("def (x, y=1, *args, option=2, **kwargs): x + y")
    assert isinstance(node, LclFunction)
    assert tuple(parameter.name for parameter in node.parameters) == tuple(
        VarName(name) for name in ("x", "y", "args", "option", "kwargs")
    )
    assert tuple(parameter.kind for parameter in node.parameters) == (
        ParameterKind.POSITIONAL,
        ParameterKind.POSITIONAL,
        ParameterKind.VAR_POSITIONAL,
        ParameterKind.KEYWORD_ONLY,
        ParameterKind.VAR_KEYWORD,
    )
    assert node.parameters[0].default is None
    assert node.parameters[1].default is not None
    assert isinstance(node.body, LclBinary)


def test_empty_function_and_nested_form_body_parse() -> None:
    """No-argument functions and complete-expression bodies are valid."""
    node = parse_expression("def (): assert(flag, 'disabled')")
    assert isinstance(node, LclFunction)
    assert node.parameters == ()
    assert isinstance(node.body, LclAssert)


def test_raise_and_assert_call_like_forms() -> None:
    """Error forms have explicit value and optional-message boundaries."""
    raised = parse_expression("raise(Error('failed'))")
    asserted = parse_expression("assert(value > 0, 'positive')")
    assert isinstance(raised, LclRaise)
    assert isinstance(raised.value, LclCall)
    assert isinstance(asserted, LclAssert)
    assert asserted.message is not None
    assert isinstance(parse_expression("assert(flag)"), LclAssert)


def test_parentheses_allow_forms_in_nested_expression_context() -> None:
    """A grouped form can appear where the ordinary parser requests an atom."""
    node = parse_expression("[(raise(error))]")
    assert isinstance(node, LclList)
    assert isinstance(node.elements[0], LclRaise)


@pytest.mark.parametrize(
    "source",
    [
        "def x: x",
        "def (x, x): x",
        "def (x=1, y): x",
        "def (**kwargs, x): x",
        "def (*args=1): x",
        "def (x)",
        "raise()",
        "raise(value",
        "assert()",
        "assert(value, message, extra)",
    ],
)
def test_invalid_form_reports_syntax_error(source: str) -> None:
    """Malformed parameter and call-like form boundaries are rejected."""
    with pytest.raises(LclSyntaxError) as caught:
        parse_expression(source)
    assert caught.value.span is not None


@pytest.mark.parametrize("source", ["def (__arg): __arg", "def (**__kwargs): 1"])
def test_double_underscore_function_bindings_are_rejected(source: str) -> None:
    """Reserved double-underscore names cannot become function bindings."""
    with pytest.raises(LclSyntaxError, match="double underscore"):
        parse_expression(source)
