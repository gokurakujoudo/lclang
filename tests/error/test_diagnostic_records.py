"""Public diagnostic record validation and source snapshot identity contracts."""

from dataclasses import replace
from typing import Any, cast

import pytest

from lclang.common.source_location import (
    UNKNOWN_SPAN,
    SourcePosition,
    SourceSpan,
    merge_source_spans,
)
from lclang.error import (
    ConfigLoadFrame,
    DiagnosticValue,
    EvaluationContextFrame,
    LclError,
    LclSyntaxError,
    LclValidationError,
)
from lclang.lang import SourceSnapshot


@pytest.mark.parametrize(
    ("record", "fields", "exception"),
    [
        (DiagnosticValue, {"name": 1}, LclValidationError),
        (DiagnosticValue, {"span": "position"}, LclValidationError),
        (DiagnosticValue, {"masked": 1}, LclValidationError),
        (DiagnosticValue, {"type_name": ""}, LclValidationError),
        (DiagnosticValue, {"name": ""}, LclValidationError),
        (EvaluationContextFrame, {"name": 1}, LclValidationError),
        (EvaluationContextFrame, {"span": "position"}, LclValidationError),
        (EvaluationContextFrame, {"masked": 1}, LclValidationError),
        (EvaluationContextFrame, {"used_values": []}, LclValidationError),
        (EvaluationContextFrame, {"used_values": (1,)}, LclValidationError),
        (EvaluationContextFrame, {"name": ""}, LclValidationError),
        (EvaluationContextFrame, {"kind": "unknown"}, LclValidationError),
        (ConfigLoadFrame, {"origin": 1}, LclValidationError),
        (ConfigLoadFrame, {"declaration_span": 1}, LclValidationError),
        (ConfigLoadFrame, {"target": 1}, LclValidationError),
    ],
)
def test_records_reject_invalid_untyped_fields(
    record: type[object], fields: dict[str, object], exception: type[Exception]
) -> None:
    """Invalid host-created metadata fails before entering the diagnostic pipeline."""
    defaults: dict[str, object]
    if record is DiagnosticValue:
        defaults = {"name": "x", "span": UNKNOWN_SPAN, "type_name": "int", "value": "1"}
    elif record is EvaluationContextFrame:
        defaults = {"name": "result", "span": UNKNOWN_SPAN, "expression": "x / 0"}
    else:
        defaults = {"origin": UNKNOWN_SPAN.origin}
    with pytest.raises(exception):
        cast(Any, record)(**(defaults | fields))


def test_source_snapshot_is_keyword_only_and_not_part_of_span_equality() -> None:
    """Source coordinates retain equality and caller-owned origin identity."""
    snapshot = SourceSnapshot("x", SourcePosition(1, 1, 0))
    span = replace(UNKNOWN_SPAN, snapshot=snapshot)
    assert span == UNKNOWN_SPAN
    assert hash(span) == hash(UNKNOWN_SPAN)
    assert span.origin is UNKNOWN_SPAN.origin
    assert merge_source_spans(span, span).snapshot is snapshot
    for text, start in ((1, snapshot.start), ("x", 1)):
        with pytest.raises(LclValidationError):
            cast(Any, SourceSnapshot)(text, start)
    with pytest.raises(LclValidationError):
        cast(Any, SourceSpan)(span.origin, span.start, span.end, snapshot)
    with pytest.raises(LclValidationError, match="snapshot"):
        replace(span, snapshot=cast(Any, "text"))


@pytest.mark.parametrize(
    "arguments",
    [
        {"message": 1},
        {"message": "failed", "code": 1},
        {"message": "failed", "span": 1},
        {"message": "failed", "config_stack": (1,)},
        {"message": "failed", "evaluation_context": []},
    ],
)
def test_errors_validate_diagnostic_metadata(arguments: dict[str, object]) -> None:
    """Exception APIs retain runtime type validation for untyped callers."""
    with pytest.raises(LclValidationError):
        cast(Any, LclError)(**arguments)


def test_adding_load_frames_copies_class_cause_traceback_and_custom_message() -> None:
    """A new load placement cannot alter another caller's original exception."""
    original = LclSyntaxError("my custom message", code="APPLICATION1")
    cause = ValueError("external reason")
    try:
        raise original from cause
    except LclSyntaxError:
        pass
    original.add_note("user note")
    context = ConfigLoadFrame(UNKNOWN_SPAN.origin, UNKNOWN_SPAN, "child.lclcfg")
    derived = original.derive_config_context(context)
    assert type(derived) is type(original)
    assert derived.code == "APPLICATION1"
    assert derived.message == "my custom message"
    assert derived.__cause__ is cause
    assert derived.__traceback__ is original.__traceback__
    assert derived.__notes__ == ["user note"]
    derived.add_note("caller note")
    assert original.__notes__ == ["user note"]
    assert original.config_stack == ()
    with pytest.raises(LclValidationError):
        original.derive_config_context(cast(Any, 1))
    derived.attach_evaluation_context(())
    derived.attach_evaluation_context(())
    first = EvaluationContextFrame("result", UNKNOWN_SPAN, "x / 0")
    derived.attach_evaluation_context((first,))
    derived.attach_evaluation_context((EvaluationContextFrame("new", UNKNOWN_SPAN, "new"),))
    assert derived.evaluation_context == (first,)
    assert "external reason" in str(derived)


def test_native_loading_copy_keeps_cause_notes_and_missing_source_metadata() -> None:
    """Native validation failures remain native and retain independent annotations."""
    from lclang.error.loading_context import derive_loading_error

    original = ValueError("invalid namespace")
    original.add_note("original note")
    derived = derive_loading_error(original, ConfigLoadFrame(UNKNOWN_SPAN.origin))
    assert isinstance(derived, LclError)
    assert derived.code == "LCL323891"
    assert derived.__cause__ is original
    assert "Cause: ValueError: invalid namespace" in str(derived)
    derived.add_note("caller note")
    assert original.__notes__ == ["original note"]


def test_native_and_unspecified_actions_have_consistent_headers() -> None:
    """Host boundaries and the generic public error retain original reason wording."""
    from lclang.error import render_failure

    assert str(LclError("user text")) == "Error [LCL000000]:\nCause: user text"
    assert render_failure(ValueError("user text"), action="loading calendar") == (
        "Error in loading calendar [LCL022890]:\nCause: ValueError: user text"
    )
