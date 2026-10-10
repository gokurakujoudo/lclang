"""Opt-in UTF-8 filesystem resolver for configuration sources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from lclang.config.sources import ResolvedConfigSource
from lclang.error import LclConfigError, LclConfigUsingError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.configuration import Code as configuration_codes
from lclang.error.wrapping import wrap_failure


@guard_constructor(LclValidationError, configuration_codes.NATIVE_321)
@dataclass(frozen=True, slots=True)
class FileConfigResolver:
    """Read canonical configuration paths from the local filesystem.

    :param allowed_root: Optional canonical containment boundary.

    .. note::
       Retrieval performs no globbing, environment expansion, or network I/O.
    """

    allowed_root: Path | None = None

    @guard_failure(LclValidationError, configuration_codes.NATIVE_321)
    def __post_init__(self) -> None:
        """Canonicalize the optional allowed-root boundary.

        :returns: ``None``.

        .. note::
           Canonicalization does not require the boundary to exist yet.
        """
        if self.allowed_root is not None:
            object.__setattr__(self, "allowed_root", self.allowed_root.resolve(strict=False))

    @guard_async_failure(LclConfigError, configuration_codes.NATIVE_321)
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
        :raises LclConfigUsingError: If the path escapes *allowed_root*.
        :raises LclConfigUsingError: If the path cannot be read as a regular file.
        :raises LclConfigUsingError: If bytes are not UTF-8 with optional BOM.

        .. note::
           Blocking filesystem work is delegated away from the event loop.
        """
        del importer
        return await asyncio.to_thread(read_file_source, path, self.allowed_root)


@guard_failure(LclConfigError, configuration_codes.NATIVE_321)
def read_file_source(path: Path, allowed_root: Path | None) -> ResolvedConfigSource:
    """Read and decode one source outside the async event-loop thread.

    :param path: Requested canonical configuration path.
    :param allowed_root: Optional containment boundary.
    :returns: Immutable decoded source snapshot.
    :raises LclConfigUsingError: If the path escapes *allowed_root*.
    :raises LclConfigUsingError: If the requested path does not exist.
    :raises LclConfigUsingError: If the requested path is a directory.
    :raises LclConfigUsingError: If the path is not a regular file or cannot be read.
    :raises LclConfigUsingError: If bytes are not UTF-8 with optional BOM.

    .. note::
       A UTF-8 BOM is accepted only because decoding starts at byte zero.
    """
    try:
        normalized = path.resolve(strict=False)
        if allowed_root is not None and not normalized.is_relative_to(allowed_root):
            raise LclConfigUsingError(
                "config path is outside the allowed root",
                code=configuration_codes.E21_CONFIG_PATH_IS_OUTSIDE_THE_ALLOWED_ROOT,
            )
        status = normalized.stat()
        if S_ISDIR(status.st_mode):
            raise LclConfigUsingError(
                f"config path is a directory: {normalized}",
                code=configuration_codes.E21_READ_FILE_SOURCE_FAILURE,
            )
        if not S_ISREG(status.st_mode):
            raise LclConfigUsingError(
                f"config path is not a regular file: {normalized}",
                code=configuration_codes.E21_CONFIG_PATH_IS_NOT_A_REGULAR_FILE_VALUE,
            )
        text = normalized.read_bytes().decode("utf-8-sig")
        return ResolvedConfigSource(str(normalized), str(normalized), normalized, text)
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as error:
        if isinstance(error, FileNotFoundError):
            code = configuration_codes.FILE_MISSING
        elif isinstance(error, PermissionError):
            code = configuration_codes.FILE_PERMISSION
        elif isinstance(error, UnicodeDecodeError):
            code = configuration_codes.FILE_ENCODING
        else:
            code = configuration_codes.FILE_READ_FAILURE
        raise wrap_failure(error, LclConfigUsingError, code) from error
