"""Failure trees retain frozen reasons and redact inherited group contexts."""

from copy import copy

from lclang.error import LclError, LclErrorGroup
from lclang.error.diagnostic_records import DiagnosticValue, EvaluationContextFrame
from lclang.lang.common.source_location import UNKNOWN_SPAN


def test_native_reason_is_frozen_and_compact_repr_does_not_expand_the_scene() -> None:
    """Re-rendering uses the owner's captured cause rather than invoking native str again."""

    class ChangingCause(ValueError):
        calls = 0

        def __str__(self) -> str:
            self.calls += 1
            return f"original cause {self.calls}"

    cause = ChangingCause()
    error = LclError("callback failed", code="APP/FAILED")
    error.__cause__ = cause
    error.freeze_native_cause(cause)
    error.verbose_failure_id = "F-scene"
    first = str(error)
    assert str(error) == str(copy(error)) == first
    assert cause.calls == 1
    assert "[APP/FAILED: original cause 1] (failure F-scene)" in repr(error)
    assert "\n" not in repr(error) and "Operation: callback failed" in first


def test_group_mask_redacts_member_expression_values_reasons_and_notes() -> None:
    """Parent masking protects all descendants without mutating their raw snapshots."""
    value = DiagnosticValue("token", UNKNOWN_SPAN, "str", "'private value'", source="external")
    context = EvaluationContextFrame("secret", UNKNOWN_SPAN, "'private expression'", (value,))
    member = LclError("private reason", evaluation_context=(context,))
    member.add_note("private note")
    group = LclErrorGroup("private group", [member])
    group.masked = True
    text = str(group)
    assert "private" not in text and "*masked*" in text
    assert member.evaluation_context[0].expression == "'private expression'"
    assert not member.masked


def test_manual_read_snapshot_does_not_guess_its_source() -> None:
    """A detached value without operation provenance is explicitly unknown."""
    value = DiagnosticValue("input", UNKNOWN_SPAN, "int", "3")
    context = EvaluationContextFrame("RESULT", UNKNOWN_SPAN, "input / 0", (value,))
    error = LclError("division by zero", evaluation_context=(context,))
    assert "input: (int) 3 (unknown)" in str(error)
    assert value.source == "unknown"
