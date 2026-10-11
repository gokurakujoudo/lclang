"""Python itself invokes installed hooks for uncaught application failures."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

SCRIPT = """import asyncio
import sys
import threading
from lclang.lang import define_frame, define_module
from lclang.logger import install_exception_hooks

async def business():
    async def callback():
        async with define_frame(define_module("inner", {"value": "1 / 0"})) as inner:
            return await inner.get("value")
    module = define_module("outer", {"RESULT": "callback()"})
    async with define_frame(module, preset={"callback": callback}) as request:
        return await request.get("RESULT")

def service():
    return asyncio.run(business())

mode, style = sys.argv[1:]
if mode == "loop":
    loop = asyncio.new_event_loop()
    install_exception_hooks(loop=loop, traceback_style=style)
    task = loop.create_task(business())
    loop.run_until_complete(asyncio.wait({task}))
    del task
    loop.close()
elif mode == "thread":
    install_exception_hooks(traceback_style=style)
    thread = threading.Thread(target=service, name="billing-worker")
    thread.start()
    thread.join()
else:
    install_exception_hooks(traceback_style=style)
    service()
"""


@pytest.mark.parametrize("mode", ["main", "thread", "loop"])
@pytest.mark.parametrize("style", ["compact", "full"])
def test_actual_uncaught_failures_use_selected_python_frame_policy(mode: str, style: str) -> None:
    """All user callback frames survive while language implementation frames are optional."""
    with TemporaryDirectory() as directory:
        source = Path(directory) / "application.py"
        source.write_text(SCRIPT, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-B", str(source), mode, style],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    assert result.returncode == (1 if mode == "main" else 0)
    assert result.stdout == ""
    assert "division by zero" in result.stderr
    assert "application.py" in result.stderr and "in business" in result.stderr
    assert "in callback" in result.stderr and "Python traceback:" in result.stderr
    frames = [line for line in result.stderr.splitlines() if 'File "' in line]
    if mode != "loop":
        assert any("asyncio" in frame for frame in frames)
    assert any("lclang" in frame for frame in frames) is (style == "full")
    assert result.stderr.count("Source:") == 1
    if mode == "thread":
        assert "billing-worker" in result.stderr
