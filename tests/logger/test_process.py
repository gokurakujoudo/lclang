"""Independent processes and thread counts preserve complete unique file records."""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.mark.parametrize("threads", [1, 10, 100])
def test_independent_processes(threads: int) -> None:
    """Separate spawned interpreters own different permanent paths and queues."""
    with TemporaryDirectory() as directory:
        env = {**os.environ, "PYTHONPATH": str(Path("src").resolve())}
        children = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.logger.process_worker",
                    directory,
                    name,
                    str(threads),
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for name in ("one", "two")
        ]
        try:
            for child in children:
                stdout, stderr = child.communicate(timeout=30)
                assert child.returncode == 0, (stdout, stderr)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait()
        paths = list(Path(directory).glob("*.log"))
        assert len(paths) == 2
        for name in ("one", "two"):
            path = next(path for path in paths if path.name.startswith(f"lclang.{name}."))
            lines = path.read_text(encoding="utf-8").splitlines()
            assert lines[0].startswith("log file: ")
            assert {line.split(" | ")[-1] for line in lines[1:]} == {
                f"record:{name}:{number}:{index}"
                for number in range(threads)
                for index in range(20)
            }
            assert len(lines) == threads * 20 + 1
