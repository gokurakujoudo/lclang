"""Framework traceback summaries preserve native evidence without LCL paragraphs."""

from typing import Literal

import pytest

from lclang.error import LclError, LclErrorGroup
from lclang.error.failure_traceback import render_failure_traceback


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
