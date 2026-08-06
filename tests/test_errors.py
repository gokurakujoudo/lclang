"""Behavioural tests for structured pylcl errors."""

from __future__ import annotations

import pytest

from pylcl.errors import LclError, LclNameError, LclSyntaxError
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


@pytest.mark.parametrize(("message", "code"), [("", "LCL0000"), ("failure", "")])
def test_error_rejects_empty_message_or_code(message: str, code: str) -> None:
    """Structured errors must never lose their human or machine identifier."""
    with pytest.raises(ValueError):
        LclError(message, code=code)
