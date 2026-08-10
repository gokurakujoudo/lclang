"""Cycle-safe async coordination for configuration source expansion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from lclang.config.errors import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigUsingError,
)
from lclang.config.limits import ConfigLoadLimits
from lclang.config.model import ConfigDefinition, ConfigUsing
from lclang.config.parser import parse_document
from lclang.config.protocols import ConfigSourceResolver
from lclang.config.result import Config
from lclang.config.sources import (
    LoadedConfigSource,
    ResolvedConfigSource,
    canonical_config_path,
    resolve_using_path,
)
from lclang.errors import LclConfigError
from lclang.source import SourceOrigin
from lclang.types import SourceName


@dataclass(slots=True)
class ConfigLoader:
    """Coordinate one event-loop-local resolver cache and expansion policy.

    :param resolver: Async path-backed source resolver.
    :param limits: Resource ceilings for unique parsing and recursive expansion.
    :param loop: Event loop captured by first use.
    :param tasks: Per-path source owner tasks.
    :param identities: Successfully parsed snapshots by stable identity.
    :param characters: Accounted decoded characters.
    :param declarations: Accounted parsed declarations.

    .. note::
       Loader state is reusable only within one event loop.
    """

    resolver: ConfigSourceResolver
    limits: ConfigLoadLimits = field(default_factory=ConfigLoadLimits)
    loop: asyncio.AbstractEventLoop | None = None
    tasks: dict[Path, asyncio.Task[LoadedConfigSource]] = field(default_factory=dict)
    identities: dict[str, LoadedConfigSource] = field(default_factory=dict)
    characters: int = 0
    declarations: int = 0

    async def load(self, path: str | Path) -> Config:
        """Load and recursively expand one root configuration path.

        :param path: Root `.lclcfg` path.
        :returns: Immutable fully expanded configuration snapshot.
        :raises LclConfigError: If retrieval, parsing, expansion, or limits fail.
        :raises LclConfigLifecycleError: If reused across event loops.

        .. note::
           Each call expands cached documents again at every using placement.
        """
        self.ensure_loop()
        root = await self.source_for(canonical_config_path(path), None)
        expanded = await self.expand(root, (), 1)
        return Config(root.document.version, root.document.origin, tuple(expanded))

    def ensure_loop(self) -> None:
        """Bind first use to the current event loop and reject cross-loop reuse.

        :returns: ``None``.
        :raises LclConfigLifecycleError: If the loader belongs to another loop.

        .. note::
           Construction outside an event loop is valid until first use.
        """
        current = asyncio.get_running_loop()
        if self.loop is None:
            self.loop = current
        elif self.loop is not current:
            raise LclConfigLifecycleError("config loader cannot cross event loops")

    async def source_for(
        self,
        path: Path,
        importer: ResolvedConfigSource | None,
    ) -> LoadedConfigSource:
        """Return one shielded single-flight resolved and parsed source.

        :param path: Canonical requested source path.
        :param importer: Source containing the using declaration, if any.
        :returns: Immutable resolved/parsed source pair.
        :raises LclConfigLimitError: If another distinct path exceeds limits.
        :raises LclConfigUsingError: If the resolver fails.

        .. note::
           Shielding isolates a waiter cancellation from the shared owner task.
        """
        task = self.tasks.get(path)
        if task is None:
            if len(self.tasks) >= self.limits.max_sources:
                raise LclConfigLimitError("config source limit exceeded")
            task = asyncio.create_task(self.resolve_and_parse(path, importer))
            self.tasks[path] = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.cancelled() and self.tasks.get(path) is task:
                self.tasks.pop(path, None)
            raise
        except Exception:
            if self.tasks.get(path) is task:
                self.tasks.pop(path, None)
            raise

    async def resolve_and_parse(
        self,
        path: Path,
        importer: ResolvedConfigSource | None,
    ) -> LoadedConfigSource:
        """Own resolver retrieval, unique accounting, and parsing.

        :param path: Canonical requested source path.
        :param importer: Source containing the using declaration, if any.
        :returns: Immutable resolved and parsed source snapshot.
        :raises LclConfigLimitError: If character or declaration limits fail.
        :raises LclConfigUsingError: If host retrieval fails.
        :raises LclConfigError: If parsing raises another config failure.

        .. note::
           Only successful immutable snapshots enter the identity cache.
        """
        try:
            source = await self.resolver.resolve(path, importer=importer)
        except asyncio.CancelledError:
            raise
        except LclConfigError:
            raise
        except Exception as error:
            raise LclConfigUsingError(f"cannot load config source {path}") from error
        existing = self.identities.get(source.identity)
        if existing is not None:
            return existing
        new_characters = self.characters + len(source.text)
        if new_characters > self.limits.max_characters:
            raise LclConfigLimitError("config character limit exceeded")
        origin = SourceOrigin(SourceName(source.display_name), source.path)
        document = parse_document(source.text, origin)
        new_declarations = self.declarations + len(document.declarations)
        if new_declarations > self.limits.max_declarations:
            raise LclConfigLimitError("config declaration limit exceeded")
        loaded = LoadedConfigSource(source, document)
        self.characters = new_characters
        self.declarations = new_declarations
        self.identities[source.identity] = loaded
        return loaded

    async def expand(
        self,
        loaded: LoadedConfigSource,
        stack: tuple[str, ...],
        depth: int,
    ) -> list[ConfigDefinition]:
        """Expand a parsed document at one source-order placement.

        :param loaded: Resolved and parsed document to expand.
        :param stack: Ordered active resolver identities.
        :param depth: One-based expansion depth including the root.
        :returns: Chronological definition occurrences.
        :raises LclConfigCycleError: If the identity is already active.
        :raises LclConfigLimitError: If depth exceeds policy.

        .. note::
           A cached document is still traversed for each source-order placement.
        """
        if depth > self.limits.max_depth:
            raise LclConfigLimitError("config using depth limit exceeded")
        identity = loaded.source.identity
        if identity in stack:
            start = stack.index(identity)
            cycle = (*stack[start:], identity)
            raise LclConfigCycleError("config using cycle: " + " -> ".join(cycle))
        active = (*stack, identity)
        output: list[ConfigDefinition] = []
        for declaration in loaded.document.declarations:
            if isinstance(declaration, ConfigDefinition):
                output.append(declaration)
                continue
            assert isinstance(declaration, ConfigUsing)
            target = resolve_using_path(declaration.target, loaded.source)
            child = await self.source_for(target, loaded.source)
            output.extend(await self.expand(child, active, depth + 1))
        return output
