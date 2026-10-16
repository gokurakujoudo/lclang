"""Applications choose compact default layouts independently for each logging call."""

import asyncio
import io
import logging
from tempfile import TemporaryDirectory

import pytest

from lclang.error import LclError, LclValidationError
from lclang.logger import use_logger, use_logger_handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["log", "debug", "info", "warning", "error", "critical", "exception"]
)
async def test_methods_select_compact_per_call_in_both_sinks(method: str) -> None:
    """All emission methods retain prefixes and arguments without changing later calls."""
    stream = io.StringIO()
    with TemporaryDirectory() as directory:
        async with use_logger_handler(
            {
                "console": {"stream": stream, "level": "DEBUG"},
                "file": {"app": {"directory": directory, "level": "DEBUG"}},
            }
        ) as runtime:
            logger = await use_logger("batch.operations", prefix="[BATCH]")
            emit = getattr(logger, method)
            args = (
                (logging.WARNING, "Task %s", "started")
                if method == "log"
                else ("Task %s", "started")
            )
            extra = {"lclang_event": "started", "business_id": 3}
            emit(*args, compact=True, extra=extra, exc_info=False)
            logger.info("Task detail", compact=False)
            logger.info("Default detail")
            assert extra == {"lclang_event": "started", "business_id": 3}
        path = runtime.metrics.sinks["file.app"].path
        assert path is not None
        file_lines = (await asyncio.to_thread(path.read_text, encoding="utf-8")).splitlines()[1:]
    lines = stream.getvalue().splitlines()
    assert lines == file_lines
    assert len(lines) == 3 and len(lines[0].split(" | ")) == 4
    assert lines[0].endswith(" | [BATCH] Task started")
    assert all(" | batch.operations | " in line for line in lines[1:])
    assert all(f"{__name__}.py:" in line for line in lines[1:])
    assert lines[1].endswith(" | [BATCH] Task detail")
    assert lines[2].endswith(" | [BATCH] Default detail")


@pytest.mark.asyncio
async def test_compact_preserves_custom_layouts_and_exception_trees() -> None:
    """Explicit layouts remain authoritative while compact errors keep their diagnostics."""
    stream = io.StringIO()
    async with use_logger_handler(
        {"format": "%(name)s %(levelname)s %(funcName)s %(message)s", "console": {"stream": stream}}
    ):
        logger = await use_logger("custom")
        logger.warning("start", compact=True)
    assert stream.getvalue() == (
        "custom WARN test_compact_preserves_custom_layouts_and_exception_trees start\n"
    )
    stream = io.StringIO()
    error = LclError("failed operation", code="APP/BATCH")
    async with use_logger_handler({"console": {"stream": stream}}):
        logger = await use_logger("batch")
        try:
            raise error
        except LclError:
            logger.exception("Task failed", compact=True)
    text = stream.getvalue()
    assert len(text.splitlines()[0].split(" | ")) == 4
    assert text.splitlines()[0].endswith(" | Task failed")
    assert text.count("[APP/BATCH: failed operation]") >= 1
    assert text.count("Python traceback:") == 1
    assert error.__traceback__ is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, 0, 1, "yes"])
async def test_compact_rejects_non_boolean_values(value: object) -> None:
    """Untyped callers receive the shared logger flag error before emitting a record."""
    stream = io.StringIO()
    async with use_logger_handler({"console": {"stream": stream}}) as runtime:
        logger = await use_logger()
        with pytest.raises(LclValidationError) as caught:
            logger.info("invalid", compact=value)  # type: ignore[arg-type]
        assert caught.value.code == "LCL612141"
        assert "compact: expected bool" in str(caught.value)
    assert stream.getvalue() == "" and runtime.metrics.records_enqueued == 0
