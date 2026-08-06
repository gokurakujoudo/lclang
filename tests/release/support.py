"""Fixtures for compact release archive policy tests."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

DIST_INFO = "pylcl-0.1.0.dist-info"


def wheel_fixture(path: Path, extra: tuple[str, ...] = ()) -> Path:
    """Write a minimal valid or deliberately extended wheel fixture.

    :param path: Destination wheel archive.
    :param extra: Additional member names used for rainy cases.
    :returns: The written archive path.
    """
    metadata = (
        "Metadata-Version: 2.4\nName: pylcl\nVersion: 0.1.0\n"
        "Requires-Python: >=3.14\nLicense-Expression: MIT\n"
    )
    values = {
        "pylcl/__init__.py": b"__version__ = '0.1.0'\n",
        "pylcl/_version.py": b"__version__ = '0.1.0'\n",
        "pylcl/py.typed": b"",
        "LICENSE": b"MIT License\n",
        f"{DIST_INFO}/METADATA": metadata.encode(),
        f"{DIST_INFO}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{DIST_INFO}/RECORD": b"",
    }
    values.update({name: b"unexpected" for name in extra})
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in values.items():
            archive.writestr(name, value)
    return path


def sdist_fixture(path: Path, extra: tuple[str, ...] = ()) -> Path:
    """Write a compact valid or deliberately extended source fixture.

    :param path: Destination gzip-compressed tar archive.
    :param extra: Additional member paths used for rainy cases.
    :returns: The written archive path.
    """
    prefix = "pylcl-0.1.0/"
    names = [
        "AGENTS.md", "CHANGELOG.md", "LICENSE", "README.md", "README_cn.md",
        "progress.md", "pyproject.toml", "pylcl/py.typed", "docs/index.md",
        "doc_cn/index.md", "tests/index.py",
    ]
    names.extend(extra)
    with tarfile.open(path, "w:gz") as archive:
        for relative in names:
            value = relative.encode()
            member = tarfile.TarInfo(prefix + relative)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return path
