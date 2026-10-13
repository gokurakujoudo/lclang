"""Verbose destination and rendering failures preserve public execution behavior."""

import asyncio

import pytest

from lclang.error import LclEvaluationError, LclNameError
from lclang.lang import define_frame, define_module
from lclang.lang.engine.evaluator.display_capture import capture_runtime_display
from lclang.lang.engine.parser import parse_expression
from lclang.logger import use_verbose
from tests.logger.verbose_support import capture_logger
from tests.support.verbose_failures import FailingVerboseLogger


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["probe", "write", "handler"])
async def test_broken_verbose_destinations_preserve_values_and_cached_failures(
    boundary: str,
) -> None:
    """Successful work and original errors survive broken DEBUG destinations."""
    logger = FailingVerboseLogger(boundary)
    async with define_frame(
        define_module("app", {"answer": "input + 2", "bad": "1 / 0"}),
        preset={"input": 40},
    ) as frame:
        with pytest.raises(LclEvaluationError) as original:
            await frame.get("bad")
        with use_verbose(logger):
            parsed = define_module("parsed", {"number": "42"})
            async with define_frame(parsed) as parsed_frame:
                assert await parsed_frame.get("number") == 42
            assert await frame.get("input") == 40
            assert await frame.get("answer") == 42
            assert await frame.get("answer") == 42
            assert await frame.evaluate("input + 2") == 42
            with pytest.raises(LclEvaluationError) as cached:
                await frame.get("bad")
            assert cached.value is original.value
            assert isinstance(cached.value.__cause__, ZeroDivisionError)
            with pytest.raises(LclEvaluationError) as recalculated:
                await frame.recalculate("bad")
            assert recalculated.value.code == "LCL131421"
            assert isinstance(recalculated.value.__cause__, ZeroDivisionError)
            with pytest.raises(LclNameError, match="unknown variable: missing"):
                await frame.get("missing")
        assert await frame.get("answer") == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "lclang.lang.engine.parser.parse_tracing.render_source_location",
        "lclang.lang.engine.evaluator.evaluation_tracing.render_source_location",
        "lclang.error.verbose_records.describe_verbose_context",
        "lclang.lang.engine.evaluator.display_requests.render_definition_location",
        "lclang.lang.engine.evaluator.display_requests.finish_display_request",
        "lclang.lang.runtime.frame.binding_evaluation.render_binding_payload",
    ],
)
async def test_verbose_rendering_failures_cannot_replace_success(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    """Failures before record emission cannot poison a successful evaluation cache."""

    def fail(*args: object, **kwargs: object) -> str:
        """Simulate an unavailable diagnostic renderer."""
        raise RuntimeError("diagnostic renderer failed")

    monkeypatch.setattr(target, fail)
    logger, _ = capture_logger()
    with use_verbose(logger):
        async with define_frame(define_module("app", {"answer": "40 + 2"})) as frame:
            assert await frame.get("answer") == 42
            assert await frame.get("answer") == 42
            assert await frame.evaluate("40 + 2") == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "lclang.error.verbose_failure.describe_failure_reason",
        "lclang.lang.engine.evaluator.display_requests.render_failure_summary",
        "lclang.error.verbose_propagation.emit_verbose_failure_batch",
    ],
)
async def test_verbose_failure_rendering_preserves_original_cached_error(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    """Failure rendering and final summaries retain the original cached exception."""

    def fail(*args: object, **kwargs: object) -> str:
        """Simulate an unavailable failure-summary renderer."""
        raise RuntimeError("diagnostic failure reporting failed")

    logger, _ = capture_logger()
    async with define_frame(define_module("app", {"bad": "1 / 0"})) as frame:
        with pytest.raises(LclEvaluationError) as original:
            await frame.get("bad")
        monkeypatch.setattr(target, fail)
        with use_verbose(logger):
            for _ in range(2):
                with pytest.raises(LclEvaluationError) as observed:
                    await frame.get("bad")
                assert observed.value is original.value
                assert observed.value.code == "LCL131421"
                assert isinstance(observed.value.__cause__, ZeroDivisionError)


@pytest.mark.parametrize(
    "signal",
    [
        asyncio.CancelledError(),
        SystemExit(7),
        KeyboardInterrupt(),
        StopIteration(),
        StopAsyncIteration(),
        ExceptionGroup("control", [StopAsyncIteration()]),
    ],
)
@pytest.mark.parametrize("boundary", ["probe", "write"])
def test_verbose_destination_native_controls_still_propagate(
    signal: BaseException, boundary: str
) -> None:
    """The diagnostic isolation boundary does not swallow native control signals."""
    logger = FailingVerboseLogger(boundary, signal)
    with pytest.raises(type(signal)) as caught, use_verbose(logger):
        parse_expression("42")
    assert caught.value is signal


@pytest.mark.asyncio
async def test_explicit_display_failures_remain_visible_without_poisoning_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit display output keeps its error contract and successful evaluation cache."""
    failure = RuntimeError("explicit display renderer failed")

    def fail(*args: object, **kwargs: object) -> None:
        """Fail the explicitly requested display publication."""
        raise failure

    monkeypatch.setattr(
        "lclang.lang.engine.evaluator.display_requests.finish_display_request", fail
    )
    logger, _ = capture_logger()
    async with define_frame(define_module("app", {"answer": "40 + 2"})) as frame:
        with (
            capture_runtime_display(),
            use_verbose(logger),
            pytest.raises(LclEvaluationError) as caught,
        ):
            await frame.get("answer")
        assert caught.value.__cause__ is failure
        assert await frame.get("answer") == 42
