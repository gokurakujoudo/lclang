"""Fault isolation across startup, output, flushing and recovery."""

import asyncio
import io
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from lclang.logger import use_logger, use_logger_handler
from lclang.logger.console import ConsoleSink
from lclang.logger.file import FileSink


def test_failed_file_startup_restores_logging_and_closes_partial_sinks() -> None:
    """Failure after one successful file leaves no live writer or global takeover."""
    with TemporaryDirectory() as directory:
        blocked = Path(directory) / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        original = logging.root.handlers

        async def exercise() -> None:
            with pytest.raises(OSError):
                async with use_logger_handler(
                    {
                        "file": {
                            "first": {"directory": directory},
                            "second": {"directory": blocked},
                        }
                    }
                ):
                    pass
            assert logging.root.handlers is original
            async with use_logger_handler({"console": {"enabled": False}}):
                await use_logger()

        asyncio.run(exercise())


@pytest.mark.parametrize("stderr", [None, io.StringIO()])
def test_console_failures_do_not_stop_files(stderr: io.StringIO | None) -> None:
    """Write and final flush errors are counted independently of successful files."""
    with TemporaryDirectory() as directory:

        async def exercise() -> None:
            with (
                patch.object(ConsoleSink, "write", side_effect=OSError),
                patch.object(ConsoleSink, "close", side_effect=OSError),
                patch("sys.__stderr__", stderr),
            ):
                async with use_logger_handler(
                    {"file": {"app": {"directory": directory}}}
                ) as runtime:
                    (await use_logger()).info("file survives")
                assert runtime.metrics.records_written == 1
                assert runtime.metrics.writer_errors == 2

        asyncio.run(exercise())
        assert "file survives" in next(Path(directory).glob("*.log")).read_text()


def test_failed_file_write_and_failed_recovery_do_not_stop_console() -> None:
    """A failed record is not replayed; a later record recovers into a new segment."""
    with TemporaryDirectory() as directory:
        console = io.StringIO()
        original_write, original_close = FileSink.write, FileSink.close
        failures = 0

        def write(sink: FileSink, record: logging.LogRecord) -> None:
            nonlocal failures
            if failures == 0:
                failures += 1
                raise OSError("write failed")
            original_write(sink, record)

        def close(sink: FileSink) -> None:
            nonlocal failures
            original_close(sink)
            if failures == 1:
                failures += 1
                raise OSError("close failed")

        async def exercise() -> None:
            with patch.object(FileSink, "write", write), patch.object(FileSink, "close", close):
                async with use_logger_handler(
                    {"console": {"stream": console}, "file": {"app": {"directory": directory}}}
                ) as runtime:
                    logger = await use_logger()
                    logger.info("lost in file")
                    logger.info("recovered")
                assert runtime.metrics.records_written == 2
                assert runtime.metrics.writer_errors == 2

        asyncio.run(exercise())
        texts = [path.read_text() for path in Path(directory).glob("*.log")]
        assert sum("recovered" in text for text in texts) == 1
        assert all("lost in file" not in text for text in texts)
        assert "lost in file" in console.getvalue()


def test_failed_header_closes_new_stream_and_reports_startup_error() -> None:
    """Header failure cannot publish a usable scope or leak its partial stream."""
    stream = io.BytesIO()

    async def exercise() -> None:
        with (
            patch("lclang.logger.segments.Path.mkdir"),
            patch("lclang.logger.segments.Path.open", return_value=stream),
            patch("lclang.logger.segments.path_line", side_effect=OSError("header")),
            pytest.raises(OSError, match="header"),
        ):
            async with use_logger_handler({"file": {"app": {"directory": "."}}}):
                pass
        assert stream.closed

    asyncio.run(exercise())


def test_timer_error_is_reported_without_killing_dispatcher() -> None:
    """A periodic flush failure cannot prevent later event processing."""
    with TemporaryDirectory() as directory:

        async def exercise() -> None:
            original = FileSink.process_timers
            failed = False

            def timer(sink: FileSink, monotonic: float, wall: float) -> None:
                nonlocal failed
                if not failed:
                    failed = True
                    raise OSError("timer")
                original(sink, monotonic, wall)

            with patch.object(FileSink, "process_timers", timer):
                async with use_logger_handler(
                    {"console": {"enabled": False}, "file": {"app": {"directory": directory}}}
                ) as runtime:
                    (await use_logger()).info("after timer")
                assert runtime.metrics.records_written == 1
                assert runtime.metrics.writer_errors == 1

        asyncio.run(exercise())
