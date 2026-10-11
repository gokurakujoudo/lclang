"""Real requests distinguish concise events from complete failure evidence."""

import io
import logging

import pytest

from lclang.error import LclError, LclErrorGroup
from lclang.error.diagnostic_records import EvaluationContextFrame
from lclang.lang import define_frame, define_module
from lclang.lang.common.source_location import UNKNOWN_SPAN
from lclang.lang.runtime.frame.default_frame_scope import create_default_frame, default_scope
from lclang.logger import LclExceptionFormatter, use_verbose
from lclang.utils import DefaultBinding


@pytest.mark.asyncio
async def test_native_default_factory_runs_once_with_verbose_enabled() -> None:
    """Generated call targets need no printable LCL syntax to execute normally."""
    calls = 0

    async def factory() -> object:
        nonlocal calls
        calls += 1
        return 39

    logger = logging.Logger("factory", logging.DEBUG)
    output = io.StringIO()
    logger.addHandler(logging.StreamHandler(output))
    async with (
        define_frame() as frame,
        create_default_frame({"amount": DefaultBinding(factory=factory)}) as defaults,
    ):
        with default_scope(frame, defaults), use_verbose(logger):
            assert await frame.get("amount") == 39
            assert await frame.get("amount") == 39
    assert calls == 1
    assert "factory" in output.getvalue()
    assert "Read amount from cache" in output.getvalue()


@pytest.mark.asyncio
async def test_each_new_evaluation_has_one_completion_without_a_second_read() -> None:
    """Successful computation keeps a root tree and explicit later cache read."""
    output = io.StringIO()
    logger = logging.Logger("revision", logging.DEBUG)
    handler = logging.StreamHandler(output)
    handler.setFormatter(LclExceptionFormatter("%(levelname)s | %(message)s"))
    logger.addHandler(handler)
    module = define_module("pricing", {"RESULT": "total + 1", "total": "amount * 2"})
    async with define_frame(module, preset={"amount": 3}) as frame:
        with use_verbose(logger):
            assert await frame.get("RESULT") == 7
            assert await frame.get("RESULT") == 7
    text = output.getvalue()
    assert text.count("Evaluated total:") == 1
    assert text.count("Evaluation tree for RESULT") == 1
    assert "a new LCL evaluation" not in text
    assert "Read RESULT from cache" in text


@pytest.mark.asyncio
async def test_native_attribute_await_failure_retains_the_actual_phase_and_cause() -> None:
    """Non-call awaitables keep their native failure and are read only once."""
    calls = 0

    async def failing_input() -> object:
        raise ValueError("remote input failed")

    class Input:
        @property
        def value(self) -> object:
            nonlocal calls
            calls += 1
            return failing_input()

    output = io.StringIO()
    logger = logging.Logger("input", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(output))
    async with define_frame(
        define_module("input", {"RESULT": "input.value"}), preset={"input": Input()}
    ) as frame:
        with use_verbose(logger), pytest.raises(LclError) as caught:
            await frame.get("RESULT")
    assert calls == 1 and isinstance(caught.value.__cause__, ValueError)
    assert "remote input failed" in str(caught.value)
    assert "Phase: awaiting expression result" in output.getvalue()


def test_same_failure_id_wrapper_keeps_the_inner_cause_and_new_context() -> None:
    """Correlation does not hide a different object carrying the same failure."""
    inner = LclError(
        "division by zero",
        code="APP/DIVIDE",
        evaluation_context=(EvaluationContextFrame("total", UNKNOWN_SPAN, "amount / divisor"),),
    )
    inner.verbose_failure_id = "F-same"
    inner.__cause__ = ZeroDivisionError("division by zero")
    outer = LclError("request failed", code=inner.code)
    outer.verbose_failure_id = inner.verbose_failure_id
    outer.__cause__ = inner
    text = str(outer)
    assert "ZeroDivisionError: division by zero" in text
    assert "total: amount / divisor" in text
    assert "request failed" in text


def test_error_group_shares_only_identical_evaluation_prefixes() -> None:
    """Member ordering, reasons and distinct tails survive prefix factoring."""
    common = EvaluationContextFrame("RESULT", UNKNOWN_SPAN, "collect_failures()")
    members = [
        LclError(
            "division by zero",
            evaluation_context=(
                common,
                EvaluationContextFrame(name, UNKNOWN_SPAN, expression),
            ),
        )
        for name, expression in (("left", "10 / 0"), ("right", "20 / 0"))
    ]
    text = str(LclErrorGroup("Two calculations failed", members))
    assert text.count("RESULT: collect_failures()") == 1
    assert text.index("left: 10 / 0") < text.index("right: 20 / 0")


@pytest.mark.asyncio
async def test_python_callback_location_and_nested_request_are_retained() -> None:
    """The callback is an actual invocation parent and has a Python definition."""
    module = define_module("callbacks", {"RESULT": "callback(3)", "inner": "1 / 0"})

    async def callback(amount: int) -> object:
        assert amount == 3
        return await frame.get("inner")

    async with define_frame(module, preset={"callback": callback}) as frame:
        with pytest.raises(LclError) as caught:
            await frame.get("RESULT")
        text = str(caught.value)
    assert "test_diagnostic_revisions.py" in text
    assert "0x" not in text
    assert "arg[0]: (int) 3 (argument)" in text
    assert text.index("callback:") < text.index("inner: 1 / 0")
