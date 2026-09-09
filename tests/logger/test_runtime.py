"""Process ownership, formatting, thread dispatch, and immutable file behavior."""

import asyncio
import io
import logging
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.logger import LoggerHandlerConfig, use_logger, use_logger_handler


@pytest.mark.asyncio
async def test_scope_formats_and_restores() -> None:
    """Prefix and traceback run behind a reversible root takeover."""
    stream = io.StringIO()
    root = logging.getLogger()
    handlers, level = root.handlers, root.level
    with pytest.raises(RuntimeError):
        await use_logger()
    async with use_logger_handler({"console": {"stream": stream, "level": "DEBUG"}}) as runtime:
        logger = await use_logger(prefix="[ORDER]")
        logger.info("created=%s", 3)
        try:
            raise ValueError("broken")
        except ValueError:
            logger.exception("failed")
        with pytest.raises(RuntimeError):
            async with use_logger_handler({}):
                pass
    assert root.handlers is handlers and root.level == level
    output = stream.getvalue()
    assert "[ORDER] created=3" in output
    assert output.count("[ORDER]") == 2
    assert "ValueError: broken" in output
    assert runtime.metrics.records_enqueued == runtime.metrics.records_written == 2
    with pytest.raises(RuntimeError):
        logger.info("outside")


@pytest.mark.asyncio
async def test_permanent_files_and_disabled_default() -> None:
    """Only explicitly enabled files open, and sealed files have stable successors."""
    with TemporaryDirectory() as directory:
        config = LoggerHandlerConfig(
            console={"enabled": False},
            file={
                "default": {"enabled": False, "directory": directory},
                "off": {"filename": "off.log"},
                "on": {
                    "enabled": True,
                    "filename": "on.{pid}.log",
                    "rotation": {"mode": "size", "max_bytes": 220},
                },
            },
        )
        async with use_logger_handler(config) as runtime:
            logger = await use_logger()
            for number in range(5):
                logger.info("unique-record-%d %s", number, "x" * 250)
        paths = await asyncio.to_thread(lambda: sorted(Path(directory).glob("*.log")))
        assert len(paths) == 5
        assert all(path.name.startswith("on.") for path in paths)
        texts = [path.read_text() for path in paths]
        assert all(text.startswith("log file: ") for text in texts)
        assert sum("continued in:" in text for text in texts) == 4
        assert runtime.metrics.rollover_count == 4
        assert sum(text.count("unique-record-") for text in texts) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("threads", [1, 10, 100])
async def test_threads_do_not_format_or_write(threads: int) -> None:
    """The complete producer set reaches the writer without caller-side formatting."""
    stream = io.StringIO()
    writer_names: set[str] = set()

    class Message:
        def __str__(self) -> str:
            writer_names.add(threading.current_thread().name)
            return "record"

    async with use_logger_handler({"console": {"stream": stream}}) as runtime:
        logger = await use_logger()

        def produce() -> None:
            for _ in range(20):
                logger.info(Message())

        workers = [threading.Thread(target=produce) for _ in range(threads)]
        for worker in workers:
            worker.start()
        await asyncio.gather(*(asyncio.to_thread(worker.join) for worker in workers))
    assert writer_names == {"lclang.logger.writer"}
    assert runtime.metrics.records_enqueued == runtime.metrics.records_written == threads * 20
