"""Framework traceback summaries preserve native evidence without LCL paragraphs."""

from types import FunctionType
from typing import Literal

import pytest

from lclang.error import LclError, LclErrorGroup
from lclang.error.failure_traceback import render_failure_traceback
from lclang.error.native_wrap import wrap_failure


def test_native_context_cause_suppression_and_cycles_are_preserved() -> None:
    """Traceback chains retain Python context policy and safely terminate cycles."""
    native = ValueError("native operation")
    error = LclError("complete LCL diagnostic", code="APP/FAILED")
    error.verbose_failure_id = "F-test"
    error.__context__ = native
    text = render_failure_traceback(error, None)
    assert "ValueError: native operation" in text and "During handling" in text
    assert "LclError [APP/FAILED: complete LCL diagnostic] (failure F-test)" in text
    assert "Error in" not in text
    error.__suppress_context__ = True
    assert "native operation" not in render_failure_traceback(error, None)
    error.__cause__ = native
    native.__cause__ = error
    text = render_failure_traceback(error, None)
    assert "exception-chain cycle" in text and "Direct cause" in text


def test_group_stacks_retain_every_native_member_and_optional_ids() -> None:
    """LCL and native groups both retain ordered members without re-rendering LCL sources."""
    first = LclError("first detail", code="APP/FIRST")
    second = LclError("second detail", code="APP/SECOND")
    grouped = LclErrorGroup("all operations failed", [first, second])
    grouped.__cause__ = ExceptionGroup("native originals", [ValueError("one"), OSError("two")])
    text = render_failure_traceback(grouped, None)
    assert "ValueError: one" in text and "OSError: two" in text
    assert "Failure 1" in text and "Failure 2" in text
    assert "LclError [APP/FIRST: first detail]" in text
    assert "LclError [APP/SECOND: second detail]" in text
    assert "Error in" not in text


@pytest.mark.parametrize("style", ["compact", "full"])
@pytest.mark.parametrize("relation", ["cause", "context"])
def test_python_relationship_precedes_outer_stack_without_modifying_tracebacks(
    style: Literal["compact", "full"], relation: str
) -> None:
    """Both policies retain native relationships before the application's outer stack."""
    native = ValueError("native cause")
    error = LclError("outer operation", code="APP/OUTER")
    if relation == "cause":
        error.__cause__ = native
    else:
        error.__context__ = native
    try:
        raise error
    except LclError:
        traceback = error.__traceback__
    text = render_failure_traceback(error, traceback, style=style)
    label = "Direct cause" if relation == "cause" else "During handling"
    assert text.splitlines()[1] == "├─ " + label
    assert text.index("ValueError: native cause") < text.index("Traceback (most recent call last)")
    assert text.count("ValueError: native cause") == 1
    assert error.__traceback__ is traceback


@pytest.mark.parametrize("style", ["compact", "full"])
def test_identical_wrapper_stack_appears_only_under_direct_cause(
    style: Literal["compact", "full"],
) -> None:
    """A copied native stack is displayed once without changing either exception."""
    try:
        raise ValueError("original operation")
    except ValueError as native:
        error = wrap_failure(native, LclError, "APP/WRAPPED")
    original = error.__traceback__
    assert error.__cause__ is not None and original is error.__cause__.__traceback__
    text = render_failure_traceback(error, original, style=style)
    assert text.count("Traceback (most recent call last)") == 1
    assert "Direct cause" in text and "ValueError: original operation" in text
    assert error.__traceback__ is original


@pytest.mark.parametrize("style", ["compact", "full"])
def test_lcl_context_notes_precede_cause_and_stack(style: Literal["compact", "full"]) -> None:
    """Both trees retain ordered context notes ahead of cause and stack evidence."""
    try:
        raise ValueError("source")
    except ValueError as native:
        error = wrap_failure(native, LclError, "APP/WRAPPED")
    error.add_note("first")
    error.add_note("second")
    for text in (str(error), render_failure_traceback(error, error.__traceback__, style=style)):
        assert text.splitlines()[1:3] == ["├─ Context: first", "├─ Context: second"]
        assert text.index("Context: second") < text.index(
            "cause" if "Direct cause" in text else "Cause"
        )


def test_equal_rendered_frames_are_not_shared_traceback_nodes() -> None:
    """Separate failures from the same source line keep both independent stacks."""

    def fail() -> ValueError:
        try:
            raise ValueError("same operation")
        except ValueError as error:
            return error

    first, second = fail(), fail()
    error = wrap_failure(first, LclError, "APP/WRAPPED")
    error.__traceback__ = second.__traceback__
    assert error.__traceback__ is not first.__traceback__
    assert (
        render_failure_traceback(error, error.__traceback__).count(
            "Traceback (most recent call last)"
        )
        == 2
    )


def test_compact_dedup_uses_selected_nodes_and_full_retains_added_frames() -> None:
    """A wrapper-only lclang frame disappears only under the compact selection policy."""

    def add_frame(error: LclError) -> LclError:
        try:
            raise error
        except LclError:
            return error

    try:
        raise ValueError("cause")
    except ValueError as native:
        error = wrap_failure(native, LclError, "APP/WRAPPED")
    callback = FunctionType(
        add_frame.__code__, {"__name__": "lclang.test_wrapper", "LclError": LclError}
    )
    callback(error)
    original = error.__traceback__
    assert render_failure_traceback(error, original).count("Traceback (most recent call last)") == 1
    assert (
        render_failure_traceback(error, original, style="full").count(
            "Traceback (most recent call last)"
        )
        == 2
    )
    assert error.__traceback__ is original


@pytest.mark.parametrize("style", ["compact", "full"])
def test_nested_lcl_groups_and_causes_put_their_own_notes_first(
    style: Literal["compact", "full"],
) -> None:
    """Every expanded LCL node retains context before native or grouped branches."""
    member = LclError("member", code="APP/MEMBER")
    member.__cause__ = ValueError("native")
    member.add_note("member context")
    cause = LclError("cause", code="APP/CAUSE")
    cause.__cause__ = OSError("source")
    cause.add_note("cause context")
    group = LclErrorGroup("group", [member])
    group.__cause__ = cause
    group.add_note("group context")
    for text in (str(group), render_failure_traceback(group, None, style=style)):
        assert text.splitlines()[1] == "├─ Context: group context"
        assert text.index("Context: cause context") < text.index("OSError: source")
        assert text.index("Context: member context") < text.index("ValueError: native")
