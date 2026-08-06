"""Build pylcl source and wheel distributions."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_command(python: Path, output: Path) -> tuple[str, ...]:
    """Create the portable package-build command.

    :param python: Python interpreter containing the build frontend.
    :param output: Artifact output directory.
    :returns: Command passed to the operating system.
    """
    return (str(python), "-m", "build", "--outdir", str(output), str(ROOT))


def main(argv: list[str] | None = None) -> int:
    """Build package artifacts without deleting existing caller data.

    :param argv: Optional command arguments.
    :returns: Build frontend return code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    options = parser.parse_args(argv)
    options.output.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        build_command(Path(sys.executable), options.output),
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
