"""Run the fail-fast, no-publication pylcl 0.2 release-candidate gate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

from scripts.build_package import build_package, ensure_empty_output
from scripts.inspect_package import (
    VERSION,
    ArtifactReport,
    inspect_sdist,
    inspect_wheel,
    normalized_wheel_members,
)
from scripts.smoke_install import smoke_install


def safe_extract(source: Path, destination: Path) -> Path:
    """Extract a validated source distribution beneath a temporary directory.

    :param source: Validated source distribution archive.
    :param destination: Empty temporary extraction directory.
    :returns: Extracted package root.
    :raises ValueError: If a member would escape *destination*.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source, "r:gz") as archive:
        root = destination / f"pylcl-{VERSION}"
        for member in archive.getmembers():
            if not member.isfile() and not member.isdir():
                raise ValueError("sdist contains a link or special archive member")
            target = destination / member.name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("sdist member escapes extraction directory")
        archive.extractall(destination)
    return root


def build_sdist_wheel(python: Path, root: Path, output: Path) -> int:
    """Build a wheel from an extracted sdist without network access.

    :param python: Python interpreter containing the build frontend.
    :param root: Extracted sdist project root.
    :param output: New or empty derived-wheel directory.
    :returns: Build frontend return code.
    """
    ensure_empty_output(output)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PIP_NO_INDEX"] = "1"
    command = (
        str(python), "-m", "hatchling", "build", "--target", "wheel",
        "--directory", str(output),
    )
    return subprocess.run(command, cwd=root, env=environment, check=False).returncode


def artifact_record(reports: tuple[ArtifactReport, ...]) -> str:
    """Serialize exact artifact evidence as one stable JSON line.

    :param reports: Validated artifact reports with public fields.
    :returns: Machine-readable JSON evidence.
    """
    values = [
        {"kind": report.kind, "name": report.path.name, "bytes": report.path.stat().st_size,
         "sha256": report.digest, "members": len(report.members)}
        for report in reports
    ]
    return json.dumps({"version": VERSION, "artifacts": values}, sort_keys=True)


def run_release(output: Path, python: Path = Path(sys.executable)) -> int:
    """Build, inspect, rebuild, and smoke-test the 0.2 artifacts.

    :param output: New or empty caller-selected release output directory.
    :param python: Python interpreter used for build and smoke tooling.
    :returns: Zero only after every release-candidate stage succeeds.

    .. note::
       The gate never publishes, tags, commits, deletes caller data, or marks
       a milestone complete.
    """
    try:
        ensure_empty_output(output)
        if build_package(python, output):
            return 1
        sdist = output / f"pylcl-{VERSION}.tar.gz"
        wheel = output / f"pylcl-{VERSION}-py3-none-any.whl"
        expected = {sdist.name, wheel.name}
        actual = {entry.name for entry in output.iterdir()}
        if actual != expected:
            raise ValueError("build output does not contain exactly the two release artifacts")
        source_report = inspect_sdist(sdist)
        wheel_report = inspect_wheel(wheel)
        temporary = output.parent / f"pylcl-release-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            extracted = safe_extract(sdist, temporary)
            derived_output = temporary / "derived-wheel"
            if build_sdist_wheel(python, extracted, derived_output):
                return 1
            derived = derived_output / wheel.name
            inspect_wheel(derived)
            if normalized_wheel_members(wheel) != normalized_wheel_members(derived):
                raise ValueError("source and sdist-derived wheels have different members")
            if smoke_install(wheel, "source-wheel") or smoke_install(derived, "sdist-wheel"):
                return 1
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        print(artifact_record((source_report, wheel_report)))
        print(json.dumps({"status": "PASS", "metadata": wheel_report.metadata}, sort_keys=True))
        return 0
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f"release-candidate failure: {error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Parse release-gate arguments and return the fail-fast status.

    :param argv: Optional command arguments.
    :returns: Zero only when the complete gate passes.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(argv)
    return run_release(options.output.resolve())


if __name__ == "__main__":
    sys.exit(main())
