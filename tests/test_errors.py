"""Behavioural tests for structured pylcl errors."""

from __future__ import annotations

import pytest

from pylcl.errors import LclError, LclEvaluationError, LclNameError, LclSyntaxError
from pylcl.source import SourceOrigin, SourcePosition, SourceSpan
from pylcl.types import SourceName


def test_error_without_span_has_stable_code_and_rendering() -> None:
    """A plain error must remain machine-readable and concise for humans."""
    error = LclNameError("missing variable")
    assert error.code == "LCL2001"
    assert error.message == "missing variable"
    assert str(error) == "[LCL2001] missing variable"
    assert isinstance(error, LclError)


def test_error_with_span_renders_source_start() -> None:
    """Source diagnostics must use logical name and one-based coordinates."""
    origin = SourceOrigin(SourceName("config.lcl"))
    span = SourceSpan(
        origin,
        SourcePosition(line=3, column=7, offset=10),
        SourcePosition(line=3, column=8, offset=11),
    )
    error = LclSyntaxError("unexpected token", span=span, code="CUSTOM")
    assert str(error) == "config.lcl:3:7: [CUSTOM] unexpected token"


def test_evaluation_error_renders_an_immutable_variable_stack() -> None:
    """An attached owner path remains ordered and on one diagnostic line."""
    error = LclEvaluationError(
        "division by zero",
        variable_stack=("RESULT", "middle", "failing"),
    )
    assert error.variable_stack == ("RESULT", "middle", "failing")
    assert str(error) == (
        "[LCL3001] division by zero "
        "[variable evaluation stack: RESULT -> middle -> failing]"
    )
    error.attach_variable_stack(("replacement",))
    assert error.variable_stack == ("RESULT", "middle", "failing")

    empty = LclEvaluationError("failure")
    empty.attach_variable_stack(("RESULT",))
    assert empty.variable_stack == ("RESULT",)
    with pytest.raises(TypeError):
        empty.attach_variable_stack(["invalid"])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        empty.attach_variable_stack(("",))


@pytest.mark.parametrize("stack", [("",), ("value", 1), ["value"]])
def test_error_rejects_invalid_variable_stacks(stack: object) -> None:
    """Variable diagnostics accept only immutable non-empty string names."""
    with pytest.raises((TypeError, ValueError)):
        LclEvaluationError("failure", variable_stack=stack)  # type: ignore[arg-type]


@pytest.mark.parametrize(("message", "code"), [("", "LCL0000"), ("failure", "")])
def test_error_rejects_empty_message_or_code(message: str, code: str) -> None:
    """Structured errors must never lose their human or machine identifier."""
    with pytest.raises(ValueError):
        LclError(message, code=code)
