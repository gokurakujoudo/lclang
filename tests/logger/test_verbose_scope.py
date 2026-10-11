"""Public verbose scopes preserve evaluation behavior and correlate failures."""

import asyncio
import copy
import io
import logging

import pytest

from lclang.error import LclError, LclErrorGroup, LclValidationError
from lclang.lang import define_frame, define_module
from lclang.logger import LoggerHandlerConfig, use_logger, use_logger_handler, use_verbose
from tests.logger.verbose_support import capture_logger


@pytest.mark.asyncio
async def test_scope_switch_suppresses_nested_tracing_and_restores_parent() -> None:
    """One call site can disable tracing without changing the outer selection."""
    logger, output = capture_logger()
    async with define_frame(preset={"outer": 1, "quiet": 2, "muted": 3, "last": 4}) as frame:
        with use_verbose(logger, enabled=True):
            assert await frame.get("outer") == 1
            with use_verbose(logger, enabled=False):
                assert await frame.get("quiet") == 2
            with use_verbose(None):
                assert await frame.get("muted") == 3
            assert await frame.get("last") == 4
        assert await frame.get("quiet") == 2
    text = output.getvalue()
    assert "outer" in text and "last" in text
    assert "quiet" not in text and "muted" not in text


@pytest.mark.parametrize("enabled", [0, 1, "yes", None])
def test_scope_rejects_non_boolean_switch(enabled: object) -> None:
    """The public switch rejects truthy substitutes at runtime."""
    logger, _ = capture_logger()
    with (
        pytest.raises(LclValidationError, match="enabled.*Boolean"),
        use_verbose(logger, enabled=enabled),  # type: ignore[arg-type]
    ):
        pass


def test_scope_rejects_invalid_logger() -> None:
    """An invalid borrowed sink is diagnosed before entering the scope."""
    with (
        pytest.raises(LclValidationError, match="logger"),
        use_verbose(object()),  # type: ignore[arg-type]
    ):
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled, level", [(False, logging.DEBUG), (True, logging.INFO)])
async def test_disabled_trace_does_not_render_host_values(enabled: bool, level: int) -> None:
    """A disabled scope or producer threshold avoids trace-only repr calls."""

    class Observed:
        """Count representation attempts without participating in arithmetic."""

        calls = 0

        def __repr__(self) -> str:
            self.calls += 1
            return "observed"

    value = Observed()
    logger, output = capture_logger(level)
    async with define_frame(preset={"value": value}) as frame:
        with use_verbose(logger, enabled=enabled):
            assert await frame.get("value") is value
    assert value.calls == 0 and output.getvalue() == ""


@pytest.mark.asyncio
async def test_failure_identity_survives_cache_scopes_copy_and_group_derivation() -> None:
    """One failed scene is referenced rather than re-expanded during later reads."""
    logger, output = capture_logger()
    async with define_frame(
        define_module("pricing", {"total": "amount / divisor", "RESULT": "total"}),
        preset={"amount": 39, "divisor": 0},
    ) as frame:
        with use_verbose(logger):
            with pytest.raises(LclError) as caught:
                await frame.get("RESULT")
            first = caught.value
            identity = first.verbose_failure_id
            assert identity is not None
            assert identity in str(first)
            with pytest.raises(LclError) as cached:
                await frame.get("RESULT")
            assert cached.value is first
        before = output.getvalue()
        with use_verbose(logger), pytest.raises(LclError) as later:
            await frame.get("RESULT")
        assert later.value.verbose_failure_id == identity
        assert copy.copy(first).verbose_failure_id == identity
        grouped = LclErrorGroup("combined", [first])
        derived = grouped.subgroup(LclError)
        assert derived is not None
        member = derived.exceptions[0]
        assert isinstance(member, LclError) and member.verbose_failure_id == identity
        assert "Failed while evaluating total" in before
        assert before.count("Failed while evaluating") == 1
        assert "Cached failures: total, RESULT" in before
        assert "cache" in output.getvalue()[len(before) :]
        assert identity in output.getvalue()[len(before) :]
        assert "Cause:" not in output.getvalue()
        with use_verbose(logger), pytest.raises(LclError) as recalculated:
            await frame.recalculate("RESULT")
        # Recalculating the dependant still observes the same cached dependency.
        assert recalculated.value.verbose_failure_id == identity
        with use_verbose(logger), pytest.raises(LclError) as new_failure:
            await frame.recalculate("total")
        assert new_failure.value.verbose_failure_id != identity


@pytest.mark.asyncio
async def test_first_observed_cached_failure_does_not_claim_new_execution() -> None:
    """Tracing an old failure assigns an ID without fabricating its history."""
    logger, output = capture_logger()
    async with define_frame(define_module("old", {"bad": "1 / 0"})) as frame:
        with pytest.raises(LclError) as original:
            await frame.get("bad")
        assert original.value.verbose_failure_id is None
        with use_verbose(logger), pytest.raises(LclError) as cached:
            await frame.get("bad")
    assert cached.value is original.value and cached.value.verbose_failure_id is not None
    assert "cached failure" in output.getvalue()
    assert "Execution: new evaluation" not in output.getvalue()


@pytest.mark.asyncio
async def test_lclang_wrapper_keeps_prefix_and_async_writer() -> None:
    """The public scope forwards through the wrapper instead of bypassing it."""
    output = io.StringIO()
    async with use_logger_handler(
        LoggerHandlerConfig(
            level="DEBUG", format="%(message)s", console={"stream": output, "level": "DEBUG"}
        )
    ):
        logger = await use_logger("application", prefix="APP")
        async with define_frame(preset={"answer": 42}) as frame:
            with use_verbose(logger):
                assert await frame.get("answer") == 42
    assert output.getvalue().startswith("APP ")
    assert "answer" in output.getvalue()


@pytest.mark.asyncio
async def test_scope_inherits_into_child_tasks_but_isolates_siblings() -> None:
    """Inherited child tracing does not enable a separately created sibling."""
    logger, output = capture_logger()
    async with define_frame(preset={"noisy": 1, "quiet": 2}) as frame:
        quiet = asyncio.create_task(frame.get("quiet"))
        with use_verbose(logger):
            noisy = asyncio.create_task(frame.get("noisy"))
            assert await noisy == 1
        assert await quiet == 2
    assert "noisy" in output.getvalue() and "quiet" not in output.getvalue()
