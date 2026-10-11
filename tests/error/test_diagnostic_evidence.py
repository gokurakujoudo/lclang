"""Correlation and shared prefixes retain every distinct captured scene."""

from copy import copy
from dataclasses import replace

from lclang.error import EvaluationContextFrame, LclError, LclErrorGroup
from lclang.error.diagnostic_evidence import DiagnosticEvidence
from lclang.error.exception_report import contains_lcl_failure
from lclang.lang import SourceSnapshot, parse_expression


def test_group_same_failure_body_is_referenced_and_masked_members_stay_protected() -> None:
    """Same-F copies keep their member headings while expanding the physical body once."""
    node = parse_expression("amount / 0")
    member: LclError = LclError(
        "division by zero",
        span=node.span,
        evaluation_context=(EvaluationContextFrame("RESULT", node.span, "amount / 0"),),
    )
    member.verbose_failure_id = "F-copies"
    group = LclErrorGroup("shared failure", [member, copy(member)])
    text = str(group)
    assert text.count("amount / 0") == 2
    assert "(source already shown)" in text
    assert "Failure 1" in text and "Failure 2" in text
    assert text.count("failure F-copies") == 2
    group.masked = True
    protected = str(group)
    assert "amount / 0" not in protected and "division by zero" not in protected
    assert "*masked*" in protected
    assert not DiagnosticEvidence().claim_source(LclError("no source"))


def test_source_less_context_keeps_a_real_span_and_variable_path() -> None:
    """Missing expression snapshots retain physical evidence without inventing an AST."""
    span = parse_expression("1 / 0").span
    error = LclError("bad calculation", span=span, variable_stack=("RESULT", "inner"))
    text = str(error)
    assert "RESULT: <expression unavailable>" in text
    assert "inner: <expression unavailable>" in text
    assert text.count("Source:") == 1 and "1 / 0" in text


def test_equal_spans_with_different_frozen_source_are_not_factored() -> None:
    """SourceSpan equality excludes snapshots; report factoring must compare them too."""
    span = parse_expression("1 / 0").span
    changed = replace(span, snapshot=SourceSnapshot("2 / 0", span.start))
    frames = [
        EvaluationContextFrame("RESULT", selected, "amount / divisor")
        for selected in (span, changed)
    ]
    members = [
        LclError("failed", span=selected.span, evaluation_context=(selected,))
        for selected in frames
    ]
    text = str(LclErrorGroup("two sites", members))
    assert text.count("RESULT: amount / divisor") == 2
    assert "1 / 0" in text and "2 / 0" in text


def test_hook_selection_follows_visible_context_and_terminates_cycles() -> None:
    """Native wrappers are eligible only when their displayed graph contains ordinary LCL."""
    lcl: LclError = LclError("inner")
    native = ValueError("outer")
    native.__context__ = lcl
    lcl.__cause__ = native
    assert contains_lcl_failure(native)
    native.__suppress_context__ = True
    assert not contains_lcl_failure(native)
