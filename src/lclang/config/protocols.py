"""Async host boundary for retrieving path-backed configuration sources."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lclang.config.sources import ResolvedConfigSource


class ConfigSourceResolver(Protocol):
    """Resolve one canonical path into immutable Unicode source text.

    .. note::
       Implementations control authorization and retrieval, not path semantics.
    """

    async def resolve(
        self,
        path: Path,
        *,
        importer: ResolvedConfigSource | None,
    ) -> ResolvedConfigSource:
        """Retrieve one normalized configuration path.

        :param path: Canonical absolute `.lclcfg` path requested by the loader.
        :param importer: Source containing the using declaration, or ``None``.
        :returns: Immutable resolved source snapshot.
        :raises Exception: If host retrieval or authorization fails.

        .. note::
           Cancellation must propagate without translation.
        """
        ...
