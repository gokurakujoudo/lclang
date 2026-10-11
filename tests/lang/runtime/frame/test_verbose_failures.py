"""Verbose observation preserves shared work, masking and failure ownership."""

import asyncio
import logging
from typing import cast

import pytest

from lclang.error import LclError
from lclang.lang import Frame, define_frame, define_module
from lclang.lang.common.identifiers import FrameId
from lclang.lang.runtime.frame.binding_tracing import trace_cached_failure_publication
from lclang.logger import use_verbose
from tests.logger.verbose_support import RecordCapture, capture_logger


@pytest.mark.asyncio
async def test_shared_failure_records_one_scene_and_one_committed_cache() -> None:
    """Concurrent requests retain one failure and reference the original execution."""
    logger, output = capture_logger()
    records = RecordCapture()
    logger.addHandler(records)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fail() -> None:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        raise OSError("external service unavailable")

    async with define_frame(
        define_module("service", {"answer": "fail()"}), preset={"fail": fail}
    ) as frame:
        with use_verbose(logger):
            first = asyncio.create_task(frame.get("answer"), name="first caller")
            await started.wait()
            second = asyncio.create_task(frame.get("answer"), name="shared caller")
            await asyncio.sleep(0)
            release.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
    assert calls == 1 and results[0] is results[1]
    error = results[0]
    assert isinstance(error, LclError) and error.verbose_failure_id is not None
    text = output.getvalue()
    assert text.count("Reason:") == 1 and text.count("Stored the failed evaluation") == 1
    assert "Returned the failed shared evaluation of answer" in text
    summary = next(record for record in records.records if "Reason:" in record.getMessage())
    assert getattr(summary, "lclang_failure_id", None) == error.verbose_failure_id
    evaluation_id = cast(str, getattr(summary, "lclang_evaluation_id", None))
    assert evaluation_id.startswith("E")
    context = dict(cast(tuple[tuple[str, str], ...], getattr(summary, "lclang_context", None)))
    assert context["Execution"] == "new evaluation" and context["Request"] == "answer"
    assert context["Evaluation"] == evaluation_id
    assert "Task" in context and "Frames" in context and "Lookup path" in context


@pytest.mark.asyncio
async def test_missing_lookup_and_parent_definition_preserve_actual_paths() -> None:
    """The first summary identifies requester, owner and traversed Frames."""
    logger, output = capture_logger()
    async with (
        Frame(define_module("pricing", {"total": "1 / 0"}), FrameId("pricing")) as owner,
        Frame(define_module("request", {}), FrameId("request"), parent=owner) as request,
    ):
        with use_verbose(logger):
            with pytest.raises(LclError) as failed:
                await request.get("total")
            with pytest.raises(LclError) as missing:
                await request.get("absent")
        assert failed.value.verbose_failure_id is not None
        assert missing.value.verbose_failure_id is not None
    text = output.getvalue()
    assert 'Frames: requested from "request"; defined in "pricing"' in text
    assert "Lookup path: request -> pricing" in text
    assert "Execution: missing binding" in text and "Reason: unknown variable: absent" in text


@pytest.mark.asyncio
async def test_masked_external_failure_and_bad_repr_are_safe() -> None:
    """No failure reason or traced value can expose a masked input."""
    logger, output = capture_logger()

    class Broken:
        def __repr__(self) -> str:
            raise RuntimeError("repr secret")

    async def secret() -> None:
        raise ValueError("private credential")

    future = asyncio.create_task(secret())
    async with define_frame(preset={"secret!": future, "broken": Broken()}) as frame:
        with use_verbose(logger):
            assert isinstance(await frame.get("broken"), Broken)
            with pytest.raises(LclError):
                await frame.get("secret")
    assert "<repr failed: RuntimeError>" in output.getvalue()
    assert "Reason: *masked*" in output.getvalue()
    assert "private credential" not in output.getvalue() and "repr secret" not in output.getvalue()
    assert "Phase: awaiting external input" in output.getvalue()


@pytest.mark.asyncio
async def test_external_filter_can_drop_all_verbose_records_and_keep_exceptions() -> None:
    """Metadata lets an application silence tracing while its ordinary error report remains."""
    logger, output = capture_logger()

    class HideVerbose(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return not getattr(record, "lclang_verbose", False)

    logger.addFilter(HideVerbose())
    async with define_frame(define_module("app", {"bad": "1 / 0"})) as frame:
        with use_verbose(logger):
            try:
                await frame.get("bad")
            except LclError as error:
                identity = error.verbose_failure_id
                logger.exception("Application request failed")
            else:
                raise AssertionError("expected failure")
    text = output.getvalue()
    assert "Reason:" not in text and "Failed while" not in text
    assert identity is not None and f"(failure {identity})" in text
    assert text.count("Error in evaluating bad") == 1 and "ZeroDivisionError" in text


@pytest.mark.asyncio
async def test_cancelled_waiter_restores_scope_and_does_not_log_control_failure() -> None:
    """A cancelled request neither cancels shared evaluation nor leaks its scope."""
    logger, output = capture_logger()
    started, release = asyncio.Event(), asyncio.Event()

    async def work() -> int:
        started.set()
        await release.wait()
        return 42

    async with define_frame(
        define_module("app", {"answer": "work()"}), preset={"work": work, "quiet": 1}
    ) as frame:

        async def wait() -> object:
            with use_verbose(logger):
                return await frame.get("answer")

        waiter = asyncio.create_task(wait())
        await started.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        release.set()
        assert await frame.get("answer") == 42
        assert await frame.get("quiet") == 1
    assert "Reason:" not in output.getvalue() and "quiet" not in output.getvalue()
    assert "Evaluated answer" in output.getvalue()


@pytest.mark.asyncio
async def test_failure_phase_comes_from_actual_call_or_await_boundary() -> None:
    """Synchronous callbacks and asynchronous results have distinct operation phases."""
    logger, output = capture_logger()

    def call_fail() -> None:
        raise OSError("synchronous callback")

    async def await_fail() -> None:
        raise OSError("asynchronous callback")

    async with define_frame(
        define_module(
            "app", {"call": "call_fail()", "wait": "await_fail()", "comparison": "left < right"}
        ),
        preset={"call_fail": call_fail, "await_fail": await_fail, "left": [], "right": 1},
    ) as frame:
        with use_verbose(logger):
            for name in ("call", "wait", "comparison"):
                with pytest.raises(LclError):
                    await frame.get(name)
    text = output.getvalue()
    assert "Phase: calling a function" in text
    assert "Phase: awaiting function result" in text
    assert "Phase: comparison operation" in text


@pytest.mark.asyncio
async def test_task_and_frame_names_cannot_break_verbose_layout() -> None:
    """Context text is detached and escapes actual line breaks from application names."""
    logger, output = capture_logger()
    task = asyncio.current_task()
    assert task is not None
    previous = task.get_name()
    task.set_name("caller\ncontinued")
    try:
        async with Frame(
            define_module("app", {"bad": "1 / 0"}), FrameId("request\ncontinued")
        ) as frame:
            with use_verbose(logger), pytest.raises(LclError):
                await frame.get("bad")
    finally:
        task.set_name(previous)
    assert '"request\\ncontinued"' in output.getvalue()
    assert "\ncontinued" not in output.getvalue()


@pytest.mark.asyncio
async def test_cache_publication_does_not_invent_an_unobserved_failure_scene() -> None:
    """A commit notice requires an existing failure ID; first observation belongs to the read."""
    logger, output = capture_logger()
    async with define_frame(define_module("app", {"bad": "1 / 0"})) as frame:
        with pytest.raises(LclError) as caught:
            await frame.get("bad")
        assert caught.value.verbose_failure_id is None
        with use_verbose(logger):
            trace_cached_failure_publication("bad", caught.value)
        assert output.getvalue() == "" and caught.value.verbose_failure_id is None
        with use_verbose(logger), pytest.raises(LclError):
            await frame.get("bad")
    assert "Observed a cached failure" in output.getvalue()
    assert "Stored the failed evaluation" not in output.getvalue()
