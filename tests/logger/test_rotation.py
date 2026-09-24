"""Deadline scheduling, exclusive names, and permanent successor chains."""

import asyncio
import io
import logging
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from lclang.logger import LoggerHandlerConfig, use_logger, use_logger_handler
from lclang.logger.file import FileSink
from lclang.logger.formatter import RecordFormatter
from lclang.logger.metrics import Counters
from lclang.logger.rotation import RotationConfig, RotationTimer
from lclang.logger.segments import next_sequence


def test_timer_uses_monotonic_or_utc_boundaries_and_skips_missed_periods() -> None:
    """Elapsed intervals retain their phase while UTC alignment follows the wall clock."""
    relative = RotationTimer(RotationConfig("time", seconds=60), 10, 100)
    assert relative.remaining(20, 10000) == 50
    relative.advance(195, 10000)
    assert relative.deadline == 250
    aligned = RotationTimer(RotationConfig("time", seconds=3600, align=True), 10, 4000)
    assert aligned.remaining(9000, 4100) == 3100
    aligned.advance(9000, 11000)
    assert aligned.deadline == 14400


def test_time_and_size_share_one_transition_and_immutable_chain() -> None:
    """An elapsed boundary and size pressure do not create a redundant empty segment."""
    with TemporaryDirectory() as directory:
        config = LoggerHandlerConfig(
            file={
                "app": {
                    "directory": directory,
                    "rotation": {"mode": "size_or_time", "interval": "1s", "max_bytes": 1},
                }
            }
        ).resolved_files()["app"]
        counters = Counters()
        sink = FileSink("app", config, RecordFormatter("%(message)s"), counters)
        sink.write(logging.makeLogRecord({"msg": "first"}))
        first = sink.path
        deadline = sink.timer.deadline
        sink.next_flush = deadline
        sink.process_timers(deadline, 0)
        second = sink.path
        sealed = first.read_bytes()
        sink.write(logging.makeLogRecord({"msg": "second"}))
        assert sink.path == second
        sink.close()
        sink.close()
        sink.next_flush = deadline
        sink.process_timers(deadline, 0)
        assert first.read_bytes() == sealed
        assert "continued in:" in sealed.decode()
        assert counters.snapshot().rollover_count == 1
        assert len(list(Path(directory).glob("*.log"))) == 2
        sink.rollover()
        sink.close()
        assert counters.snapshot().rollover_count == 2


def test_idle_dispatcher_rotates_without_records() -> None:
    """A real queue timeout triggers file rotation with no producer wake-up."""
    with TemporaryDirectory() as directory:

        async def exercise() -> None:
            async with use_logger_handler(
                {
                    "console": {"enabled": False},
                    "file": {
                        "app": {
                            "directory": directory,
                            "rotation": {"mode": "time", "interval": "1s"},
                        }
                    },
                }
            ) as runtime:
                async with asyncio.timeout(5):
                    while (  # noqa: ASYNC110 -- observe a real worker timer
                        runtime.metrics.rollover_count == 0
                    ):
                        await asyncio.sleep(0.02)
                assert runtime.metrics.records_enqueued == 0

        asyncio.run(exercise())
        assert len(list(Path(directory).glob("*.log"))) >= 2


def test_name_collision_preserves_existing_file_and_sequence_survives_scopes() -> None:
    """Exclusive creation retries an existing pathname instead of truncating it."""
    with TemporaryDirectory() as directory:
        original_open = Path.open
        collided: list[Path] = []

        def collision(path: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
            if mode == "xb" and not collided:
                collided.append(path)
                path.write_text("historical", encoding="utf-8")
            return original_open(path, mode, *args, **kwargs)  # type: ignore[call-overload]

        async def exercise() -> None:
            for _ in range(2):
                async with use_logger_handler(
                    {"console": {"enabled": False}, "file": {"app": {"directory": directory}}}
                ):
                    (await use_logger()).info("new")

        with patch.object(Path, "open", collision):
            asyncio.run(exercise())
        assert collided[0].read_text() == "historical"
        assert len(list(Path(directory).glob("*.log"))) == 3
    with patch("lclang.logger.segments.SEQUENCE_PID", -1):
        assert next_sequence() == 1


def test_multiple_sources_and_levels_broadcast_once_per_sink() -> None:
    """Source boundaries and thresholds select independent complete files."""
    with TemporaryDirectory() as directory:
        console = io.StringIO()

        async def exercise() -> None:
            async with use_logger_handler(
                {
                    "console": {"stream": console},
                    "file": {
                        "default": {"directory": directory, "level": "DEBUG"},
                        "app": {"logger_names": ["orders"]},
                        "errors": {"level": "ERROR"},
                    },
                }
            ) as runtime:
                logger = await use_logger("orders.child")
                logger.debug("detail")
                logger.error("failure")
                (await use_logger("orders")).info("exact")
                (await use_logger("orders_extra")).debug("excluded")
            assert runtime.metrics.records_enqueued == 4
            assert runtime.metrics.records_written == 3
            assert runtime.metrics.sinks["file.app"].records_written == 3
            assert runtime.metrics.sinks["file.errors"].records_written == 1

        asyncio.run(exercise())
        assert "detail" not in console.getvalue()


def test_busy_queue_does_not_starve_deadlines() -> None:
    """Advance the clock while a preloaded batch keeps the queue continuously busy."""
    with TemporaryDirectory() as directory:
        clock = [time.monotonic()]

        class AdvancingMessage:
            def __str__(self) -> str:
                clock[0] += 0.6
                return "busy-record"

        async def exercise() -> None:
            async with use_logger_handler(
                {
                    "console": {"enabled": False},
                    "file": {
                        "app": {
                            "directory": directory,
                            "rotation": {"mode": "time", "interval": "1s"},
                        }
                    },
                }
            ) as runtime:
                logger = await use_logger()
                for _ in range(5):
                    logger.info(AdvancingMessage())
            assert runtime.metrics.records_written == 5
            assert runtime.metrics.rollover_count >= 2

        with patch(
            "lclang.logger.dispatcher.time",
            SimpleNamespace(
                monotonic=lambda: clock[0],
                time=time.time,
            ),
        ):
            asyncio.run(exercise())
        texts = [path.read_text(encoding="utf-8") for path in Path(directory).glob("*.log")]
        assert sum(text.count("busy-record") for text in texts) == 5
