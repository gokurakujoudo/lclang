"""Install a pylcl wheel into a fresh virtual environment."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def venv_python(root: Path, platform: str = os.name) -> Path:
    """Return the Python executable inside a virtual environment.

    :param root: Virtual-environment directory.
    :param platform: Operating-system family, normally :data:`os.name`.
    :returns: Interpreter path for Windows or POSIX.
    """
    if platform == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _run(command: tuple[str, ...]) -> int:
    """Run a smoke-test subprocess.

    :param command: Command and arguments.
    :returns: Child return code.
    """
    return subprocess.run(command, check=False).returncode


def smoke_install(wheel: Path) -> int:
    """Install and import one wheel in a temporary environment.

    :param wheel: Wheel artifact to verify.
    :returns: Zero when installation and import succeed.
    """
    with tempfile.TemporaryDirectory(prefix="pylcl-smoke-") as directory:
        environment = Path(directory)
        venv.EnvBuilder(with_pip=True).create(environment)
        python = str(venv_python(environment))
        install = _run((python, "-m", "pip", "install", "--no-deps", str(wheel)))
        if install:
            return install
        return _run((python, "-c", "import pylcl; print(pylcl.__version__)"))


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and execute the clean-install smoke test.

    :param argv: Optional command arguments.
    :returns: Smoke-test return code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    options = parser.parse_args(argv)
    return smoke_install(options.wheel.resolve())


if __name__ == "__main__":
    sys.exit(main())
