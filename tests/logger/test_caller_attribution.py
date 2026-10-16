"""Qualified Python caller names survive producer threads and queued formatting."""

import asyncio
import inspect
import io
import logging
import os
import threading
from tempfile import TemporaryDirectory
from types import FunctionType
from unittest.mock import patch

import pytest

from lclang.logger import use_logger, use_logger_handler
from lclang.logger.handler_config import DEFAULT_FORMAT
from lclang.logger.logging_metrics import Counters
from lclang.logger.queue_handler import LocalQueueHandler, resolve_caller_module
from lclang.logger.record_formatter import RecordFormatter


@pytest.mark.asyncio
async def test_qualified_callers_and_sink_parity() -> None:
    """Wrapper offsets and borrowed stdlib loggers retain the producing module and thread."""
    stream = io.StringIO()
    with TemporaryDirectory() as directory:
        async with use_logger_handler(
            {"console": {"stream": stream}, "file": {"app": {"directory": directory}}}
        ) as runtime:
            logger = await use_logger("arbitrary.channel")

            def business_wrapper() -> None:
                logger.warning("wrapped", stacklevel=2)

            caller = inspect.currentframe()
            assert caller is not None
            expected = caller.f_lineno + 1
            business_wrapper()
            offset_logger = await use_logger("offset.channel", emit_level=1)

            def offset_wrapper() -> None:
                offset_logger.warning("offset")

            offset_expected = caller.f_lineno + 1
            offset_wrapper()

            def produce() -> None:
                logging.getLogger("borrowed.channel").critical("borrowed\ncontinuation")

            worker = threading.Thread(target=produce, name="BusinessThread")
            worker.start()
            await asyncio.to_thread(worker.join)
        path = runtime.metrics.sinks["file.app"].path
        assert path is not None
        file_lines = (await asyncio.to_thread(path.read_text, encoding="utf-8")).splitlines()[1:]
    lines = stream.getvalue().splitlines()
    assert lines == file_lines
    assert lines[0].endswith(
        f" | WARN  | MainThread({os.getpid()}) | arbitrary.channel | "
        f"{__name__}.py:{expected}:test_qualified_callers_and_sink_parity | wrapped"
    )
    assert lines[1].endswith(
        f" | WARN  | MainThread({os.getpid()}) | offset.channel | "
        f"{__name__}.py:{offset_expected}:test_qualified_callers_and_sink_parity | offset"
    )
    assert f" | CRIT  | BusinessThread({os.getpid()}) | borrowed.channel | " in lines[2]
    assert f"{__name__}.py:{produce.__code__.co_firstlineno + 1}:produce | borrowed" in lines[2]
    assert lines[3] == "continuation"


@pytest.mark.asyncio
async def test_script_entry_point_uses_actual_module_name() -> None:
    """The producing globals determine a script's name independently of logger identity."""
    stream = io.StringIO()

    def produce() -> None:
        logging.getLogger("script.channel").info("script ready")

    script = FunctionType(produce.__code__, {"__name__": "__main__", "logging": logging})
    async with use_logger_handler({"console": {"stream": stream}}):
        script()
    assert (
        f"script.channel | __main__.py:{produce.__code__.co_firstlineno + 1}:produce | script ready"
        in stream.getvalue()
    )


@pytest.mark.asyncio
async def test_stacklevel_distinguishes_reused_code_with_different_module_globals() -> None:
    """The selected source line distinguishes cloned caller frames sharing a code object."""
    stream = io.StringIO()

    def produce(inner: bool) -> None:
        if inner:
            logging.getLogger("selected.channel").info("selected caller", stacklevel=2)
        else:
            globals()["selected"](True)

    inner = FunctionType(produce.__code__, {"__name__": "app.inner", "logging": logging})
    outer = FunctionType(
        produce.__code__, {"__name__": "app.outer", "logging": logging, "selected": inner}
    )
    async with use_logger_handler({"console": {"stream": stream}}):
        outer(False)
    assert (
        f"app.outer.py:{produce.__code__.co_firstlineno + 4}:produce | selected caller"
        in stream.getvalue()
    )


@pytest.mark.parametrize("module_name", [None, "", 3])
def test_missing_or_invalid_module_names_fall_back(module_name: object) -> None:
    """A matched caller without a usable module name retains its original filename."""

    def probe() -> None:
        handler = LocalQueueHandler(logging.NOTSET, Counters())
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "message", (), None, "probe")
        before = record.__dict__.copy()
        try:
            caller = inspect.currentframe()
            assert caller is not None
            record.lineno = caller.f_lineno + 1
            handler.emit(record)
            snapshot = handler.queue.get_nowait()
            assert snapshot is not None
            assert f"test_caller_attribution.py:{record.lineno}:probe | message" in (
                RecordFormatter(DEFAULT_FORMAT).format(snapshot)
            )
            assert record.__dict__ == {**before, "lineno": record.lineno}
        finally:
            handler.close()

    caller = FunctionType(probe.__code__, {**globals(), "__name__": module_name})
    caller()


def test_unavailable_frames_and_synthetic_records_have_no_module() -> None:
    """Non-frame records remain formattable without inspecting modules or source files."""
    record = logging.LogRecord("synthetic", logging.INFO, "absent.py", 1, "message", (), None)
    assert resolve_caller_module(record) is None
    with patch("lclang.logger.queue_handler.inspect.currentframe", return_value=None):
        assert resolve_caller_module(record) is None
