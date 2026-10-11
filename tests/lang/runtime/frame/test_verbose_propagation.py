"""Root failure summaries preserve committed caches and actual propagation."""

import asyncio
from typing import cast

import pytest

from lclang.error import LclError
from lclang.lang import Frame, define_frame, define_module
from lclang.lang.common.identifiers import FrameId
from lclang.logger import use_verbose
from tests.logger.verbose_support import RecordCapture, capture_logger


@pytest.mark.asyncio
async def test_deep_failure_has_one_root_summary_and_explicit_cache_hits() -> None:
    """One failure scene and one commit summary replace per-binding repeats."""
    logger, output = capture_logger()
    records = RecordCapture()
    logger.addHandler(records)
    module = define_module(
        "pricing",
        {
            "RESULT": "report + 1",
            "report": "invoice + 5",
            "invoice": "total + 10",
            "total": "net + 1",
            "net": "converted - 2",
            "converted": "ratio * 100",
            "ratio": "calculate(subtotal, divisor)",
            "calculate": "(amount, divisor) -> normalize(amount, divisor)",
            "normalize": "(amount, divisor) -> divide(amount, divisor)",
            "divide": "(amount, divisor) -> amount / divisor",
            "subtotal": "39",
        },
    )
    async with define_frame(module, preset={"divisor": 0}) as frame:
        assert await frame.get("subtotal") == 39
        with use_verbose(logger), pytest.raises(LclError) as first:
            await frame.get("RESULT")
        identity = first.value.verbose_failure_id
        assert identity is not None
        # Reads after the summary prove that every listed cache was committed.
        with use_verbose(logger):
            for name in ("total", "RESULT"):
                with pytest.raises(LclError) as cached:
                    await frame.get(name)
                assert cached.value is first.value
    text = output.getvalue()
    assert text.count("Failed while evaluating") == 1
    assert text.count("Could not evaluate RESULT") == 1
    assert "Stored the failed evaluation" not in text and "Could not complete" not in text
    assert "Cached failures: ratio, converted, net, total, invoice, report, RESULT" in text
    assert text.count("no new evaluation") == 2
    assert text.index("Could not evaluate RESULT") < text.index("Returned the cached failure")
    summary = next(r for r in records.records if "Could not evaluate RESULT" in r.getMessage())
    assert getattr(summary, "lclang_failure_id", None) == identity
    assert summary.levelno == 10 and summary.levelname == "DEBUG"
    context = dict(cast(tuple[tuple[str, str], ...], getattr(summary, "lclang_context", None)))
    assert "ratio because calculate failed" in context["Propagation"]
    assert "RESULT because report failed" in context["Propagation"]
    assert "ratio" in context["Cache owners"] and "RESULT" in context["Cache owners"]
    assert context["Request"] == "RESULT"


@pytest.mark.asyncio
async def test_recovered_failure_summary_does_not_claim_the_root_failed() -> None:
    """A handled dependency still reports its actual cache without a false outcome."""
    logger, output = capture_logger()
    async with define_frame(
        define_module("app", {"RESULT": "try: bad except: 42", "bad": "1 / 0"})
    ) as frame:
        with use_verbose(logger):
            assert await frame.get("RESULT") == 42
            with pytest.raises(LclError):
                await frame.get("bad")
    text = output.getvalue()
    assert "Failure observed while evaluating RESULT" in text
    assert "Cached failures: bad" in text
    assert "Could not evaluate RESULT" not in text
    assert "Evaluation tree for RESULT" in text
    assert "Returned the cached failure of bad; no new evaluation" in text


@pytest.mark.asyncio
async def test_concurrent_roots_keep_distinct_failure_cache_summaries() -> None:
    """Independent tasks cannot combine the affected bindings of separate failures."""
    logger, output = capture_logger()
    async with define_frame(
        define_module("app", {"left": "a + 1", "right": "b + 1", "a": "1 / 0", "b": "2 / 0"})
    ) as frame:
        with use_verbose(logger):
            errors = await asyncio.gather(
                frame.get("left"), frame.get("right"), return_exceptions=True
            )
    assert all(isinstance(error, LclError) for error in errors)
    first, second = cast(tuple[LclError, LclError], tuple(errors))
    assert first.verbose_failure_id != second.verbose_failure_id
    text = output.getvalue()
    assert (
        f"Could not evaluate left (failure {first.verbose_failure_id})\n  Cached failures: a, left"
        in text
    )
    assert (
        f"Could not evaluate right (failure {second.verbose_failure_id})\n"
        "  Cached failures: b, right" in text
    )


@pytest.mark.asyncio
async def test_unnamed_expression_and_missing_binding_do_not_invent_caches() -> None:
    """A propagated missing name can be summarized without claiming a cache commit."""
    logger, output = capture_logger()
    async with define_frame() as frame:
        with use_verbose(logger), pytest.raises(LclError):
            await frame.evaluate("missing + 1")
    text = output.getvalue()
    assert "Failed to read missing" in text
    assert "Cached failures:" not in text
    assert "Could not evaluate <expr>" not in text


@pytest.mark.asyncio
async def test_cancelled_root_does_not_swallow_later_owner_failure_events() -> None:
    """Shielded evaluation can still report commits after its caller leaves the batch."""
    logger, output = capture_logger()
    started, release = asyncio.Event(), asyncio.Event()

    async def fail() -> None:
        started.set()
        await release.wait()
        raise OSError("service unavailable")

    async with define_frame(
        define_module("app", {"bad": "fail()"}), preset={"fail": fail}
    ) as frame:
        with use_verbose(logger):
            caller = asyncio.create_task(frame.get("bad"))
            await started.wait()
            caller.cancel()
            with pytest.raises(asyncio.CancelledError):
                await caller
            release.set()
            with pytest.raises(LclError):
                await frame.get("bad")
        assert "Stored the failed evaluation of bad in cache" in output.getvalue()
        assert "Returned the failed shared evaluation of bad" in output.getvalue()
        assert "Could not evaluate bad" not in output.getvalue()
        assert "CancelledError" not in output.getvalue()
        before = output.getvalue()
        with pytest.raises(LclError):
            await frame.get("bad")
        assert output.getvalue() == before


@pytest.mark.asyncio
async def test_direct_nested_evaluation_keeps_the_actual_committing_frame() -> None:
    """A host callback may evaluate another Frame without a new binding lookup."""
    logger, _ = capture_logger()
    records = RecordCapture()
    logger.addHandler(records)
    async with Frame(define_module("inner", {"bad": "1 / 0"}), FrameId("inner")) as inner:

        async def evaluate_inner() -> object:
            return await inner.evaluate_definition("bad")

        async with Frame(
            define_module("outer", {"RESULT": "evaluate_inner()"}),
            FrameId("outer"),
            values={"evaluate_inner": evaluate_inner},
        ) as outer:
            with use_verbose(logger), pytest.raises(LclError) as failed:
                await outer.get("RESULT")
            with pytest.raises(LclError) as cached:
                await inner.get("bad")
            assert cached.value is failed.value
    summary = next(r for r in records.records if "Could not evaluate RESULT" in r.getMessage())
    context = dict(cast(tuple[tuple[str, str], ...], getattr(summary, "lclang_context", None)))
    assert context["Cache owners"] == 'bad: "inner"; RESULT: "outer"'
    assert context["Cached failures"] == "bad, RESULT"
