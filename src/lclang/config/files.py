"""Opt-in UTF-8 filesystem resolver for configuration sources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from lclang.config.sources import ResolvedConfigSource


@dataclass(frozen=True, slots=True)
class FileConfigResolver:
    """Read canonical configuration paths from the local filesystem.

    :param allowed_root: Optional canonical containment boundary.

    .. note::
       Retrieval performs no globbing, environment expansion, or network I/O.
    """

    allowed_root: Path | None = None

    def __post_init__(self) -> None:
        """Canonicalize the optional allowed-root boundary.

        :returns: ``None``.

        .. note::
           Canonicalization does not require the boundary to exist yet.
        """
        if self.allowed_root is not None:
            object.__setattr__(self, "allowed_root", self.allowed_root.resolve(strict=False))

    async def resolve(
        self,
        path: Path,
        *,
        importer: ResolvedConfigSource | None,
    ) -> ResolvedConfigSource:
        """Read and strictly decode one regular `.lclcfg` file.

        :param path: Canonical absolute requested path.
        :param importer: Importing source, retained only for protocol symmetry.
        :returns: Immutable decoded source snapshot.
        :raises PermissionError: If the path escapes *allowed_root*.
        :raises OSError: If the path cannot be read as a regular file.
        :raises UnicodeDecodeError: If bytes are not UTF-8 with optional BOM.

        .. note::
           Blocking filesystem work is delegated away from the event loop.
        """
        del importer
        return await asyncio.to_thread(read_file_source, path, self.allowed_root)


def read_file_source(path: Path, allowed_root: Path | None) -> ResolvedConfigSource:
    """Read and decode one source outside the async event-loop thread.

    :param path: Requested canonical configuration path.
    :param allowed_root: Optional containment boundary.
    :returns: Immutable decoded source snapshot.
    :raises PermissionError: If the path escapes *allowed_root*.
    :raises FileNotFoundError: If the requested path does not exist.
    :raises IsADirectoryError: If the requested path is a directory.
    :raises UnicodeDecodeError: If bytes are not UTF-8 with optional BOM.

    .. note::
       A UTF-8 BOM is accepted only because decoding starts at byte zero.
    """
    normalized = path.resolve(strict=False)
    if allowed_root is not None and not normalized.is_relative_to(allowed_root):
        raise PermissionError("config path is outside the allowed root")
    if not normalized.is_file():
        if normalized.is_dir():
            raise IsADirectoryError(str(normalized))
        raise FileNotFoundError(str(normalized))
    text = normalized.read_bytes().decode("utf-8-sig")
    return ResolvedConfigSource(str(normalized), str(normalized), normalized, text)
