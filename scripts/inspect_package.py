"""Inspect lclang release archives against current project metadata."""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path, PurePosixPath

from scripts.versioning import project_version

# Distribution version selected from authoritative project metadata.
VERSION = project_version()
# Archive members that can never be part of a clean source distribution.
FORBIDDEN_PARTS = frozenset(
    {
        "..",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".codex_tmp",
        "__pycache__",
        "build",
        "dist",
        "venv",
    }
)


@dataclass(frozen=True, slots=True)
class ArtifactReport:
    """Record normalized members and metadata for one inspected archive.

    :param path: Archive inspected on disk.
    :param kind: ``wheel`` or ``sdist``.
    :param members: Ordered archive member names.
    :param metadata: Selected normalized package metadata.
    :param digest: SHA-256 digest of the exact archive bytes.
    """

    path: Path
    kind: str
    members: tuple[str, ...]
    metadata: dict[str, str]
    digest: str


def sha256(path: Path) -> str:
    """Compute the SHA-256 digest of one archive without loading it all.

    :param path: File whose bytes are hashed.
    :returns: Lowercase hexadecimal SHA-256 digest.
    :raises OSError: If *path* cannot be read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_fields(raw: str) -> dict[str, str]:
    """Extract the release-relevant fields from wheel METADATA text.

    :param raw: RFC-style metadata text.
    :returns: Case-normalized selected metadata values.
    :raises ValueError: If the metadata does not identify the current release.
    """
    message = Parser().parsestr(raw)
    fields = {
        "Name": message.get("Name", ""),
        "Version": message.get("Version", ""),
        "Requires-Python": message.get("Requires-Python", ""),
        "License": message.get("License-Expression", "") or message.get("License", ""),
        "Requires-Dist": ",".join(message.get_all("Requires-Dist", [])),
    }
    if fields["Name"] != "lclang" or fields["Version"] != VERSION:
        raise ValueError("wheel metadata has an inconsistent name or version")
    if fields["Requires-Python"] != ">=3.14" or fields["License"] != "MIT":
        raise ValueError("wheel metadata has an inconsistent Python or license field")
    if fields["Requires-Dist"]:
        raise ValueError("wheel declares an unexpected runtime dependency")
    return fields


def wheel_member_policy(members: tuple[str, ...], dist_info: str) -> None:
    """Validate that wheel members contain only package and license files.

    :param members: Zip member names in archive order.
    :param dist_info: Expected ``.dist-info`` directory name.
    :returns: ``None`` when the member set is valid.
    :raises ValueError: If a forbidden, duplicate, or required member is found.
    """
    if len(set(members)) != len(members) or any("\\" in name for name in members):
        raise ValueError("wheel contains duplicate or non-portable member names")

    def allowed(name: str) -> bool:
        """Return whether one member belongs to the package or metadata tree."""
        return name.startswith("lclang/") or name.startswith(f"{dist_info}/")

    if any(not allowed(name) and PurePosixPath(name).name != "LICENSE" for name in members):
        raise ValueError("wheel contains a repository or build-tree member")
    required = {
        "lclang/__init__.py",
        "lclang/_version.py",
        "lclang/py.typed",
        "lclang/utils/calendar/__init__.py",
    }
    required |= {f"{dist_info}/METADATA", f"{dist_info}/WHEEL", f"{dist_info}/RECORD"}
    has_license = any(PurePosixPath(name).name == "LICENSE" for name in members)
    if not required <= set(members) or not has_license:
        raise ValueError("wheel is missing package, metadata, or license files")
    if any(name.endswith((".pyc", ".pyo")) or "__pycache__" in name for name in members):
        raise ValueError("wheel contains bytecode or cache files")


def inspect_wheel(path: Path) -> ArtifactReport:
    """Inspect one universal lclang wheel and return its release report.

    :param path: Wheel archive to inspect.
    :returns: Validated archive report.
    :raises ValueError: If filename, members, tags, or metadata drift.
    :raises OSError: If the archive cannot be read.
    """
    expected = f"lclang-{VERSION}-py3-none-any.whl"
    if path.name != expected:
        raise ValueError(f"unexpected wheel filename: {path.name}")
    with zipfile.ZipFile(path) as archive:
        members = tuple(archive.namelist())
        metadata_names = [name for name in members if name.endswith(".dist-info/METADATA")]
        wheel_names = [name for name in members if name.endswith(".dist-info/WHEEL")]
        if len(metadata_names) != 1 or len(wheel_names) != 1:
            raise ValueError("wheel must contain one metadata and one WHEEL file")
        dist_info = metadata_names[0].split("/", 1)[0]
        wheel_text = archive.read(wheel_names[0]).decode("utf-8")
        if "Tag: py3-none-any" not in wheel_text or "Root-Is-Purelib: true" not in wheel_text:
            raise ValueError("wheel is not the required universal pure-Python tag")
        metadata = metadata_fields(archive.read(metadata_names[0]).decode("utf-8"))
    wheel_member_policy(members, dist_info)
    return ArtifactReport(path, "wheel", members, metadata, sha256(path))


def sdist_member_policy(members: tuple[str, ...]) -> None:
    """Validate required clean source-distribution members.

    :param members: Tar member names in archive order.
    :returns: ``None`` when the source member set is valid.
    :raises ValueError: If the root, required trees, or exclusions are wrong.
    """
    prefix = f"lclang-{VERSION}/"
    if any(not name.startswith(prefix) for name in members):
        raise ValueError("sdist contains an unexpected archive root")
    if len(set(members)) != len(members):
        raise ValueError("sdist contains duplicate members")
    for name in members:
        parts = PurePosixPath(name).parts
        if any(part in FORBIDDEN_PARTS for part in parts) or name.endswith((".pyc", ".pyo")):
            raise ValueError("sdist contains ignored build output")
    required = {
        "AGENTS.md",
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
        "docs/reference/calendar.md",
        "docs/tutorials/README.md",
        "docs/tutorials/11-business-day-calendars.md",
        "docs/tutorials/15-energy-settlement-workflow.md",
        "progress.md",
        "pyproject.toml",
        "src/lclang/utils/calendar/__init__.py",
        "src/lclang/py.typed",
    }
    for tree in ("docs", "src/lclang", "tests"):
        if not any(name.startswith(f"{prefix}{tree}/") for name in members):
            raise ValueError(f"sdist is missing the {tree} tree")
    if not required <= {name[len(prefix) :] for name in members}:
        raise ValueError("sdist is missing a required release file")


def inspect_sdist(path: Path) -> ArtifactReport:
    """Inspect one lclang source distribution and return its release report.

    :param path: Source distribution archive to inspect.
    :returns: Validated archive report.
    :raises ValueError: If filename or members violate the source contract.
    :raises OSError: If the archive cannot be read.
    """
    expected = f"lclang-{VERSION}.tar.gz"
    if path.name != expected:
        raise ValueError(f"unexpected sdist filename: {path.name}")
    with tarfile.open(path, "r:gz") as archive:
        members = tuple(member.name for member in archive.getmembers())
    sdist_member_policy(members)
    metadata = {"Name": "lclang", "Version": VERSION}
    return ArtifactReport(path, "sdist", members, metadata, sha256(path))


def normalized_wheel_members(path: Path) -> frozenset[str]:
    """Return wheel members excluding the generated hash manifest.

    :param path: Wheel archive to normalize.
    :returns: Member paths whose semantic content should match across builds.
    :raises ValueError: If the wheel fails inspection.
    """
    report = inspect_wheel(path)
    return frozenset(name for name in report.members if not name.endswith(".dist-info/RECORD"))


def inspect_artifact(path: Path) -> ArtifactReport:
    """Dispatch inspection based on one supported artifact suffix.

    :param path: Wheel or gzip-compressed source distribution.
    :returns: Validated artifact report.
    :raises ValueError: If the suffix is unsupported or inspection fails.
    """
    if path.name.endswith(".whl"):
        return inspect_wheel(path)
    if path.name.endswith(".tar.gz"):
        return inspect_sdist(path)
    raise ValueError(f"unsupported artifact: {path}")
