"""Cross-platform path, version, archive, and subprocess release audits."""

from __future__ import annotations

import ast
import io
import tarfile
import tomllib
from pathlib import Path

import pytest

from scripts.release_candidate import safe_extract
from scripts.smoke_install import venv_python
from scripts.versioning import project_version

ROOT = Path(__file__).resolve().parents[2]


def test_release_version_comes_from_project_metadata() -> None:
    """Release maintenance reads exactly the project metadata version."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project_version() == project["version"]


def test_virtual_environment_paths_are_platform_neutral() -> None:
    """Windows and POSIX executable paths preserve spaces and Unicode."""
    root = Path("parent space") / "环境"
    assert venv_python(root, "nt") == root / "Scripts" / "python.exe"
    assert venv_python(root, "posix") == root / "bin" / "python"


@pytest.mark.parametrize("kind", (tarfile.SYMTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE))
def test_safe_extract_rejects_links_devices_and_special_members(
    tmp_path: Path,
    kind: bytes,
) -> None:
    """No non-file archive member reaches the extraction filesystem."""
    archive_path = tmp_path / "special.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("lclang-special/member")
        member.type = kind
        member.linkname = "target"
        archive.addfile(member, io.BytesIO())
    with pytest.raises(ValueError, match="link or special"):
        safe_extract(archive_path, tmp_path / "extract")


def test_release_subprocesses_never_request_shell_parsing() -> None:
    """Every checked-in subprocess invocation uses direct argument vectors."""
    for path in sorted((ROOT / "scripts").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"run", "check_call", "check_output", "Popen"}:
                continue
            shell_values = [keyword.value for keyword in node.keywords if keyword.arg == "shell"]
            assert not shell_values or all(
                isinstance(value, ast.Constant) and value.value is False for value in shell_values
            )
