"""Real HTTP integration exercises complete Uvicorn and Gunicorn worker lifecycles."""

import asyncio
import io
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import pytest
import uvicorn

from tests.documentation.examples import ROOT, execute_example, marked_blocks
from tests.logger.service_app import app


def assert_lifecycle(directory: str) -> None:
    """Verify server, lifespan, request, and background events reached the file."""
    paths = list(Path(directory).glob("*.log"))
    assert len(paths) == 1
    text = paths[0].read_text(encoding="utf-8")
    for message in (
        "Started server process",
        "service-startup",
        "service-request",
        "service-background",
        "service-shutdown",
        "Finished server process",
        "GET / HTTP/1.1",
    ):
        assert message in text


@pytest.mark.asyncio
async def test_uvicorn_complete_service_entry() -> None:
    """Windows-compatible scope surrounds serve, including server startup and exit."""
    with TemporaryDirectory() as directory, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        stream = io.StringIO()
        server = uvicorn.Server(uvicorn.Config(app, log_config=None))
        source = next(
            block
            for block in marked_blocks(
                (ROOT / "docs/reference/logger.md").read_text(encoding="utf-8")
            )
            if "async def serve(" in block
        )
        serve = cast(Any, execute_example(source, "logger.md")["serve"])
        task = asyncio.create_task(
            serve(
                server,
                {"console": {"stream": stream}, "file": {"service": {"directory": directory}}},
                sockets=[listener],
            )
        )
        try:
            async with asyncio.timeout(10):
                while not server.started:  # noqa: ASYNC110 -- Uvicorn exposes a boolean
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
            reader, writer = await asyncio.open_connection(*listener.getsockname())
            writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), 10)
            writer.close()
            await writer.wait_closed()
            assert b'"ok":true' in response
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 10)
        assert_lifecycle(directory)
        assert "service-background" in stream.getvalue()


@pytest.mark.skipif(sys.platform != "linux", reason="Gunicorn requires Linux/POSIX")
def test_gunicorn_worker_after_fork() -> None:
    """The Linux quality job exercises a real master, worker, request and SIGTERM."""
    with TemporaryDirectory() as directory, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        address = listener.getsockname()
        source = marked_blocks(
            (ROOT / "docs/reference/logger.md").read_text(encoding="utf-8"),
            marker="<!-- lclang-gunicorn-exec -->",
        )[0]
        (Path(directory) / "logging_worker.py").write_text(source, encoding="utf-8")
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(Path("src").resolve()), directory)),
            "LOGGER_DIRECTORY": directory,
        }
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "tests.logger.service_app:app",
                "--worker-class",
                "logging_worker.LoggingWorker",
                "--bind",
                f"fd://{listener.fileno()}",
                "--workers",
                "1",
                "--access-logfile",
                "-",
            ],
            pass_fds=(listener.fileno(),),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urllib.request.urlopen(
                        f"http://{address[0]}:{address[1]}/", timeout=1
                    ) as res:
                        assert b'"ok":true' in res.read()
                    break
                except urllib.error.URLError, TimeoutError:
                    assert child.poll() is None, child.communicate()
                    assert time.monotonic() < deadline
            child.send_signal(signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, (stdout, stderr)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate()
        assert_lifecycle(directory)
