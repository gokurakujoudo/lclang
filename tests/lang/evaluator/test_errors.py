"""Unit tests mirroring :mod:`lclang.lang.evaluator.errors`."""

import asyncio

import pytest

from lclang import evaluate
from lclang.ast import LclAstNode, LclConstant, LclExceptHandler
from lclang.errors import LclEvaluationError
from lclang.lang.evaluator.context import MappingResolver, Resolver
from lclang.lang.evaluator.errors import internal_matches
from lclang.lang.parser import parse_expression


@pytest.mark.asyncio
async def test_raise_creates_source_aware_error_and_cause() -> None:
    """A deliberate failure retains its node span and exception-valued cause."""
    problem = ValueError("bad value")
    node = parse_expression("raise(problem)")
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(node, {"problem": problem})
    assert caught.value.span == node.span
    assert caught.value.message == "bad value"
    assert caught.value.__cause__ is problem


@pytest.mark.asyncio
async def test_raise_accepts_non_exception_value_without_cause() -> None:
    """A scalar raised value becomes the message without inventing a cause."""
    node = parse_expression("raise(value)")
    with pytest.raises(LclEvaluationError, match="42") as caught:
        await evaluate(node, {"value": 42})
    assert caught.value.span == node.span
    assert caught.value.__cause__ is None


@pytest.mark.asyncio
async def test_assert_returns_truthy_value_and_skips_message() -> None:
    """A successful assertion returns its condition without evaluating message."""
    called = False

    def message() -> str:
        nonlocal called
        called = True
        return "unused"

    result = await evaluate(
        parse_expression("assert(value, message())"),
        {"value": "ok", "message": message},
    )
    assert result == "ok"
    assert called is False


@pytest.mark.asyncio
async def test_failed_assert_uses_lazy_message() -> None:
    """A false condition resolves its message before raising a structured error."""
    node = parse_expression("assert(value, message)")
    with pytest.raises(LclEvaluationError, match="expected value") as caught:
        await evaluate(node, {"value": False, "message": "expected value"})
    assert caught.value.span == node.span


@pytest.mark.asyncio
async def test_failed_assert_without_message_uses_default() -> None:
    """A message-free false assertion reports the stable default diagnostic."""
    node = parse_expression("assert(value)")
    with pytest.raises(LclEvaluationError, match="LCL assertion failed") as caught:
        await evaluate(node, {"value": False})
    assert caught.value.span == node.span


@pytest.mark.asyncio
async def test_typed_handler_matches_wrapped_cause_and_binds_error() -> None:
    """A matcher may recover an application exception preserved as the cause."""

    def fail() -> None:
        raise ValueError("failed")

    values: dict[str, object] = {
        "fail": fail,
        "ValueError": ValueError,
        "error": "outer",
    }
    source = "try: fail() except ValueError as error: error.message"
    assert await evaluate(parse_expression(source), values) == "ValueError: failed"
    assert values["error"] == "outer"


@pytest.mark.asyncio
async def test_handlers_use_source_order_and_bare_fallback() -> None:
    """A nonmatching typed handler falls through to the final bare handler."""

    def fail() -> None:
        raise ValueError("failed")

    source = "try: fail() except KeyError: 'wrong' except: 'recovered'"
    values = {"fail": fail, "KeyError": KeyError}
    assert await evaluate(parse_expression(source), values) == "recovered"


@pytest.mark.asyncio
async def test_bare_matcher_helper_short_circuits_evaluation() -> None:
    """The documented matcher helper accepts a bare handler without evaluating a type."""
    called = False

    async def forbidden_evaluate(node: LclAstNode, resolver: Resolver) -> object:
        """Fail if a bare handler unexpectedly evaluates a matcher."""
        nonlocal called
        del node, resolver
        called = True
        raise AssertionError("bare matcher evaluated")

    handler = LclExceptHandler(None, None, LclConstant(value=None))
    assert await internal_matches(
        handler, ValueError("problem"), MappingResolver({}), forbidden_evaluate
    )
    assert called is False


@pytest.mark.asyncio
async def test_unmatched_failure_propagates_same_public_error() -> None:
    """A try with no matching handler preserves the structured body failure."""

    def fail() -> None:
        raise ValueError("failed")

    source = "try: fail() except KeyError: None"
    values = {"fail": fail, "KeyError": KeyError}
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression(source), values)
    assert isinstance(caught.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_finally_runs_and_preserves_successful_result() -> None:
    """Successful cleanup does not replace the body or handler result."""
    events: list[str] = []

    def cleanup() -> None:
        events.append("cleanup")

    source = "try: value finally: cleanup()"
    assert await evaluate(parse_expression(source), {"value": 42, "cleanup": cleanup}) == 42
    assert events == ["cleanup"]


@pytest.mark.asyncio
async def test_finally_failure_replaces_pending_result() -> None:
    """A cleanup failure becomes the nearest source-aware public error."""

    def cleanup() -> None:
        raise RuntimeError("cleanup failed")

    with pytest.raises(LclEvaluationError, match="cleanup failed") as caught:
        await evaluate(
            parse_expression("try: 42 finally: cleanup()"),
            {"cleanup": cleanup},
        )
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_cancellation_is_not_caught_but_finally_runs() -> None:
    """Task cancellation bypasses handlers while retaining cleanup guarantees."""
    events: list[str] = []

    async def cancel() -> None:
        raise asyncio.CancelledError

    def cleanup() -> None:
        events.append("cleanup")

    source = "try: cancel() except: None finally: cleanup()"
    with pytest.raises(asyncio.CancelledError):
        await evaluate(parse_expression(source), {"cancel": cancel, "cleanup": cleanup})
    assert events == ["cleanup"]


@pytest.mark.asyncio
async def test_invalid_handler_matcher_is_wrapped() -> None:
    """A non-type matcher fails through the ordinary evaluation boundary."""

    def fail() -> None:
        raise ValueError("failed")

    source = "try: fail() except matcher: None"
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression(source), {"fail": fail, "matcher": 42})
    assert isinstance(caught.value.__cause__, TypeError)
