"""Release publication uses the package's own version and changelog."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.release_notes import release_notes


@pytest.mark.parametrize(
    ("version", "section", "error"),
    [
        ("1.0.9", "## 1.0.9 - 2026-09-09\n\n- Published change.\n", None),
        ("1.0.9rc1", "", "stable 1.0.x"),
        ("1.0.9", "## 1.0.8 - 2026-09-08\n- Old.\n", "one dated"),
        ("1.0.9", "## 1.0.9 - 2026-09-09\n\n", "empty"),
        ("1.0.9", "## 1.0.9 - 2026-09-09\n- A.\n## 1.0.9 - 2026-09-09\n- B.\n", "one dated"),
    ],
)
def test_release_notes(version: str, section: str, error: str | None) -> None:
    """Only one nonempty stable release section can be published."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "pyproject.toml").write_text(
            f'[project]\nversion = "{version}"\n', encoding="utf-8",
        )
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\n- Future.\n\n" + section + "\n## Older\n- Old.\n",
            encoding="utf-8",
        )
        if error:
            with pytest.raises(ValueError, match=error):
                release_notes(root)
        else:
            assert release_notes(root) == (version, "- Published change.\n")
