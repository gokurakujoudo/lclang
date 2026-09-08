"""Exercise the exact worker example's signal replay without a POSIX-only master."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FrameType, ModuleType
from typing import cast
from unittest.mock import patch

import pytest
import uvicorn

from tests.documentation.examples import ROOT, execute_example, marked_blocks


@pytest.mark.parametrize("shutdown", ["normal", "sigterm", "error"])
def test_documented_worker_drains_after_shutdown(shutdown: str) -> None:
    """Real Uvicorn signal capture must return through the logging scope on exit."""
    server = uvicorn.Server(uvicorn.Config("unused:app", log_config=None))

    class Worker:
        alive = True

        def init_signals(self) -> None:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)

        def handle_exit(self, sig: int, frame: FrameType | None) -> None:
            self.alive = False

        async def _serve(self) -> None:
            with server.capture_signals():
                logging.getLogger("uvicorn.error").info("worker-started")
                if shutdown == "sigterm":
                    server.handle_exit(signal.SIGTERM, None)
                logging.getLogger("worker.application").info("worker-finished")
                if shutdown == "error":
                    raise ValueError("service failed")

    replayed: list[int] = []

    def replay(sig: int) -> None:
        handler = signal.getsignal(sig)
        assert callable(handler), "SIGTERM would terminate the worker before logger drain"
        replayed.append(sig)
        handler(sig, None)

    module = ModuleType("uvicorn_worker")
    module.UvicornWorker = Worker  # type: ignore[attr-defined]
    source = marked_blocks(
        (ROOT / "docs/reference/logger.md").read_text(encoding="utf-8"),
        marker="<!-- lclang-gunicorn-exec -->",
    )[0]
    original = signal.getsignal(signal.SIGTERM)
    try:
        with (
            TemporaryDirectory() as directory,
            patch.dict(sys.modules, {"uvicorn_worker": module}),
            patch.dict("os.environ", {"LOGGER_DIRECTORY": directory}),
            patch("signal.raise_signal", side_effect=replay),
        ):
            worker = cast(type[Worker], execute_example(source, "logger.md")["LoggingWorker"])()
            worker.init_signals()
            if shutdown == "error":
                with pytest.raises(ValueError, match="service failed"):
                    asyncio.run(worker._serve())
            else:
                asyncio.run(worker._serve())
            assert replayed == ([signal.SIGTERM] if shutdown == "sigterm" else [])
            assert worker.alive == (shutdown != "sigterm")
            paths = list(Path(directory).glob("*.log"))
            assert len(paths) == 1
            text = paths[0].read_text(encoding="utf-8")
            assert text.count("worker-started") == 1
            assert text.count("worker-finished") == 1
    finally:
        signal.signal(signal.SIGTERM, original)
