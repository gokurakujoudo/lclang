"""Validate a stable package version and extract its release notes."""

import argparse
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_notes(root: Path) -> tuple[str, str]:
    """Return the stable version and its nonempty, dated changelog section."""
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
    if not re.fullmatch(r"1\.0\.(0|[1-9][0-9]*)", version):
        raise ValueError(f"Expected stable 1.0.x version, got {version!r}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}[ \t]*$"
    matches = list(re.finditer(heading, changelog, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected one dated changelog section for {version}")
    remainder = changelog[matches[0].end():]
    notes = re.split(r"^## ", remainder, maxsplit=1, flags=re.MULTILINE)[0].strip()
    if not notes:
        raise ValueError(f"Release notes are empty for {version}")
    return version, notes + "\n"


def main() -> None:
    """Write the checked-out release notes and print its version for CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    version, notes = release_notes(ROOT)
    args.output.write_text(notes, encoding="utf-8")
    print(version)


if __name__ == "__main__":
    main()
