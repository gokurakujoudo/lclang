"""Failure identities survive ordinary wrapping, explicit copying and group splitting."""

from copy import copy

import pytest

from lclang.error import LclError, LclErrorGroup, LclEvaluationError, LclSyntaxError
from lclang.error.native_wrap import wrap_failure
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.lang import define_frame
from lclang.lang.common.source_location import UNKNOWN_SPAN
from lclang.lang.engine.evaluator.ast_interpreter import interpret_expression
from lclang.lang.engine.parser import parse_expression
from lclang.lang.engine.parser.parse_tracing import trace_parse_result
from lclang.logger import use_verbose
from tests.logger.verbose_support import capture_logger


def test_group_members_have_independent_identities_and_derived_groups_keep_parent_id() -> None:
    """A first observed group explains its members once and links the final summary."""
    logger, output = capture_logger()
    first, second = LclSyntaxError("invalid source"), LclEvaluationError("callback failed")
    group = LclErrorGroup("several operations failed", [first, second])
    with use_verbose(logger):
        identity = trace_verbose_failure(
            group, "operations", phase="closing resources", stage="command"
        )
        trace_verbose_failure(group, "outer operation", phase="returning a failure")
    assert len({identity, first.verbose_failure_id, second.verbose_failure_id}) == 3
    selected, remaining = group.split(LclSyntaxError)
    assert isinstance(selected, LclErrorGroup) and isinstance(remaining, LclErrorGroup)
    assert selected.verbose_failure_id == remaining.verbose_failure_id == identity
    assert selected.exceptions == (first,) and remaining.exceptions == (second,)
    assert copy(group).verbose_failure_id == identity
    assert wrap_failure(first, LclEvaluationError, "APP/WRAPPED") is first
    target = LclSyntaxError("context added")
    first.copy_diagnostic_fields(target)
    assert target.verbose_failure_id == first.verbose_failure_id
    text = output.getvalue()
    assert text.count("Failed during") == 3 and "Members:" in text
    assert "Reason:" not in text
    assert "Cause:" not in text and "invalid source" in text and "callback failed" in text
    assert identity is not None and f"(failure {identity})" in str(selected)


def test_native_selected_members_remain_native_and_do_not_need_metadata() -> None:
    """Native derive inputs keep their arguments while the group still correlates."""
    logger, output = capture_logger()
    source = LclErrorGroup("original", [LclError("member")])
    native = ValueError("native selected member")
    derived = source.derive([native])
    assert isinstance(derived, LclErrorGroup)
    with use_verbose(logger):
        assert (
            trace_verbose_failure(derived, "derived group", phase="collecting failures") is not None
        )
    assert derived.exceptions == (native,) and derived.args[1] == [native]
    assert "Members:" in output.getvalue()


def test_masked_group_redacts_every_new_member_summary() -> None:
    """Group masking applies before members are observed for the first time."""
    logger, output = capture_logger()
    group = LclErrorGroup("private group", [LclError("private member")])
    group.masked = True
    with use_verbose(logger):
        trace_verbose_failure(group, "operation", phase="collecting failures")
    assert output.getvalue().count(": *masked*]") == 2
    assert "private" not in output.getvalue()


@pytest.mark.parametrize(
    "error",
    [
        KeyboardInterrupt(),
        SystemExit(),
        StopIteration(),
        StopAsyncIteration(),
        ExceptionGroup("control", [StopAsyncIteration()]),
    ],
)
def test_control_signals_are_not_verbose_failures(error: BaseException) -> None:
    """An enabled scope preserves control signals without ordinary failure summaries."""
    logger, output = capture_logger()
    with use_verbose(logger):
        assert trace_verbose_failure(error, "operation", phase="executing callback") is None
    assert output.getvalue() == ""


def test_parse_text_has_one_expression_unless_adaptation_changes_it() -> None:
    """Formatting distinguishes original text from canonical AST only when needed."""
    logger, output = capture_logger()
    with use_verbose(logger):
        parse_expression("1")
        node = parse_expression("1+2")
        trace_parse_result("original adaptation input", node)
    text = output.getvalue()
    assert text.count("<expr>: 1 (") == 1
    assert "Input: 1+2\n<expr>: 1 + 2 (" in text
    assert "Input: original adaptation input" in text
    assert "Parsed an expression as LclConstant" in text


@pytest.mark.asyncio
async def test_unnamed_unknown_location_result_has_no_fabricated_context() -> None:
    """Standalone implementation use need not invent a Frame or named request."""
    from dataclasses import replace

    from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT, VerboseContext
    from lclang.lang.engine.evaluator.evaluation_tracing import trace_evaluation_result

    logger, output = capture_logger()
    node = replace(parse_expression("1"), span=UNKNOWN_SPAN)
    with use_verbose(logger):
        token = ACTIVE_VERBOSE_CONTEXT.set(VerboseContext())
        try:
            trace_evaluation_result(node, 1)
        finally:
            ACTIVE_VERBOSE_CONTEXT.reset(token)
        assert await interpret_expression(node) == 1
    assert "Evaluated <expr>" in output.getvalue()
    assert "Source:" not in output.getvalue() and "Frames:" not in output.getvalue()


@pytest.mark.asyncio
async def test_verbose_and_quiet_failures_capture_the_same_read_values() -> None:
    """Verbose cannot change the diagnostic journal or probe unexecuted branches."""
    logger, _ = capture_logger()
    from lclang.lang import define_module

    snapshots: list[tuple[str, ...]] = []
    for enabled in (False, True):
        async with define_frame(
            define_module("app", {"bad": "left / right if true else unused"}),
            preset={"left": 7, "right": 0},
        ) as frame:
            with use_verbose(logger, enabled=enabled), pytest.raises(LclError) as caught:
                await frame.get("bad")
            snapshots.append(
                tuple(
                    value.name
                    for context in caught.value.evaluation_context
                    for value in context.used_values
                )
            )
            assert "unused" not in snapshots[-1]
    assert snapshots[0] == snapshots[1] and "left" in snapshots[0] and "right" in snapshots[0]
