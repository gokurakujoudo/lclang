"""Fixtures for compact release archive policy tests."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from scripts.inspect_package import VERSION

DIST_INFO = f"lclang-{VERSION}.dist-info"


def wheel_fixture(path: Path, extra: tuple[str, ...] = ()) -> Path:
    """Write a minimal valid or deliberately extended wheel fixture.

    :param path: Destination wheel archive.
    :param extra: Additional member names used for rainy cases.
    :returns: The written archive path.
    """
    metadata = (
        f"Metadata-Version: 2.4\nName: lclang\nVersion: {VERSION}\n"
        "Requires-Python: >=3.14\nLicense-Expression: MIT\n"
    )
    values = {
        "lclang/__init__.py": f"__version__ = '{VERSION}'\n".encode(),
        "lclang/_version.py": f"__version__ = '{VERSION}'\n".encode(),
        "lclang/py.typed": b"",
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
    prefix = f"lclang-{VERSION}/"
    names = [
        "AGENTS.md",
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
        "README_cn.md",
        "progress.md",
        "pyproject.toml",
        "src/lclang/py.typed",
        "docs/index.md",
        "docs/zh/README.md",
        "tests/index.py",
    ]
    names.extend(extra)
    with tarfile.open(path, "w:gz") as archive:
        for relative in names:
            value = relative.encode()
            member = tarfile.TarInfo(prefix + relative)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return path
