"""Build lclang source and wheel distributions."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The build script treats this directory as the source tree passed to Hatch.


def build_command(python: Path, output: Path, target: str) -> tuple[str, ...]:
    """Create the portable package-build command.

    :param python: Python interpreter containing the build frontend.
    :param output: Artifact output directory.
    :param target: Hatchling target, either ``wheel`` or ``sdist``.
    :returns: Command passed to the operating system.
    """
    return (str(python), "-m", "hatchling", "build", "--target", target, "--directory", str(output))


def ensure_empty_output(output: Path) -> None:
    """Create a release output directory only when it is safe to use.

    :param output: Caller-selected directory for newly built artifacts.
    :returns: ``None`` after the directory is verified empty.
    :raises ValueError: If *output* is a file or contains any entry.

    .. note::
       Existing caller files are never removed or overwritten by this check.
    """
    if output.exists() and not output.is_dir():
        raise ValueError(f"build output is not a directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"build output must be empty: {output}")


def build_package(python: Path, output: Path) -> int:
    """Build source and wheel artifacts into a safe output directory.

    :param python: Python interpreter containing the build frontend.
    :param output: New or empty artifact output directory.
    :returns: Build frontend return code.
    :raises ValueError: If *output* is not new or empty.
    """
    ensure_empty_output(output)
    wheel = subprocess.run(build_command(python, output, "wheel"), cwd=ROOT, check=False)
    if wheel.returncode:
        return wheel.returncode
    return subprocess.run(build_command(python, output, "sdist"), cwd=ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    """Build package artifacts without deleting existing caller data.

    :param argv: Optional command arguments.
    :returns: Build frontend return code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    options = parser.parse_args(argv)
    try:
        return build_package(Path(sys.executable), options.output)
    except ValueError as error:
        print(f"build failure: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
