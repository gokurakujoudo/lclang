"""Cycle-safe async coordination for configuration source expansion.

Defines ``ConfigLoader``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from lclang.common.identifiers import SourceName
from lclang.common.source_location import SourceOrigin
from lclang.config.config_document import ConfigDefinition, ConfigImport, ConfigUsing
from lclang.config.config_source import (
    LoadedConfigSource,
    ResolvedConfigSource,
    canonical_config_path,
    resolve_using_path,
)
from lclang.config.document_parser import parse_document
from lclang.config.import_qualification import qualify_import
from lclang.config.loaded_config import Config
from lclang.config.loading_limit import ConfigLoadLimits
from lclang.config.source_resolver import ConfigSourceResolver
from lclang.config.target_evaluation import evaluate_using_target, snapshot_using_overrides
from lclang.error import ConfigurationErrorCode, LclConfigError, LclError
from lclang.error.configuration_exception import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigUsingError,
)
from lclang.error.diagnostic_records import ConfigLoadFrame
from lclang.error.exception_base import LclValidationError
from lclang.error.loading_context import derive_loading_error
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure


@guard_constructor(LclValidationError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
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
    tasks: dict[Path, asyncio.Task[LoadedConfigSource]] = field(
        default_factory=dict[Path, asyncio.Task[LoadedConfigSource]]
    )
    identities: dict[str, LoadedConfigSource] = field(default_factory=dict[str, LoadedConfigSource])
    characters: int = 0
    declarations: int = 0

    @guard_async_failure(LclConfigError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
    async def load(
        self,
        path: str | Path,
        *,
        overrides: Mapping[str, object] | None = None,
    ) -> Config:
        """Load and recursively expand one root configuration path.

        :param path: Root `.lclcfg` path.
        :param overrides: Call-level literal or semantic using-target overrides.
        :returns: Immutable fully expanded configuration snapshot.
        :raises LclConfigError: If retrieval, parsing, expansion, or limits fail.
        :raises LclConfigLifecycleError: If reused across event loops.

        .. note::
           Each call expands cached documents again at every using placement.
        """
        self.ensure_loop()
        selected_overrides = snapshot_using_overrides(overrides)
        selected_path = canonical_config_path(path)
        origin = SourceOrigin(SourceName(str(selected_path)), selected_path)
        try:
            root = await self.source_for(selected_path, None)
            expanded: list[ConfigDefinition] = []
            namespaces: set[str] = set()
            await self.expand(root, (), 1, expanded, selected_overrides, namespaces)
            return Config(
                root.document.version,
                root.document.origin,
                tuple(expanded),
                namespace_names=frozenset(namespaces),
            )
        except Exception as error:
            raise derive_loading_error(error, ConfigLoadFrame(origin)) from error.__cause__

    @guard_failure(LclConfigError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
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
            raise LclConfigLifecycleError(
                "config loader cannot cross event loops",
                code=ConfigurationErrorCode.E23_CONFIG_LOADER_CANNOT_CROSS_EVENT_LOOPS,
            )

    @guard_async_failure(LclConfigError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
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
                raise LclConfigLimitError(
                    "config source limit exceeded",
                    code=ConfigurationErrorCode.E23_CONFIG_SOURCE_LIMIT_EXCEEDED,
                )
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

    @guard_async_failure(LclConfigError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
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
        :raises LclValidationError: If the resolver returns an invalid snapshot.
        :raises LclConfigUsingError: If host retrieval fails.
        :raises LclConfigError: If parsing raises another config failure.

        .. note::
           Only successful immutable snapshots enter the identity cache.
        """
        try:
            source = await self.resolver.resolve(path, importer=importer)
        except asyncio.CancelledError:
            raise
        except LclError:
            raise
        except Exception as error:
            wrapped = wrap_failure(
                error,
                LclConfigUsingError,
                ConfigurationErrorCode.E23_CANNOT_LOAD_CONFIG_SOURCE,
                message=f"cannot load config source {path}",
            )
            raise wrapped from wrapped.__cause__
        if not isinstance(source, ResolvedConfigSource):
            raise LclValidationError(
                "resolver must return a ResolvedConfigSource",
                code=ConfigurationErrorCode.E23_RESOLVER_RESULT_TYPE,
            )
        existing = self.identities.get(source.identity)
        if existing is not None:
            return existing
        new_characters = self.characters + len(source.text)
        if new_characters > self.limits.max_characters:
            raise LclConfigLimitError(
                "config character limit exceeded",
                code=ConfigurationErrorCode.E23_CONFIG_CHARACTER_LIMIT_EXCEEDED,
            )
        origin = SourceOrigin(SourceName(source.display_name), source.path)
        document = parse_document(source.text, origin)
        new_declarations = self.declarations + len(document.declarations)
        if new_declarations > self.limits.max_declarations:
            raise LclConfigLimitError(
                "config declaration limit exceeded",
                code=ConfigurationErrorCode.E23_CONFIG_DECLARATION_LIMIT_EXCEEDED,
            )
        loaded = LoadedConfigSource(source, document)
        self.characters = new_characters
        self.declarations = new_declarations
        self.identities[source.identity] = loaded
        return loaded

    @guard_async_failure(LclConfigError, ConfigurationErrorCode.E23_CONFIG_LOADING_NATIVE_FAILURE)
    async def expand(
        self,
        loaded: LoadedConfigSource,
        stack: tuple[str, ...],
        depth: int,
        output: list[ConfigDefinition],
        overrides: Mapping[str, object],
        namespaces: set[str] | None = None,
    ) -> None:
        """Expand a parsed document at one source-order placement.

        :param loaded: Resolved and parsed document to expand.
        :param stack: Ordered active resolver identities.
        :param depth: One-based expansion depth including the root.
        :param output: Call-local chronological definitions accumulated in place.
        :param overrides: Call-level using-target overrides.
        :param namespaces: Call-local explicit namespace reservations.
        :returns: ``None`` after appending chronological definitions.
        :raises LclConfigCycleError: If the identity is already active.
        :raises LclValidationError: If a loading declaration has an invalid type.
        :raises LclConfigLimitError: If depth exceeds policy.
        :raises LclConfigError: If a required source is missing or any source is invalid.

        .. note::
           A cached document is still traversed for each source-order placement.
        """
        if namespaces is None:
            namespaces = set()
        if depth > self.limits.max_depth:
            raise LclConfigLimitError(
                "config using depth limit exceeded",
                code=ConfigurationErrorCode.E23_CONFIG_USING_DEPTH_LIMIT_EXCEEDED,
            )
        identity = loaded.source.identity
        if identity in stack:
            start = stack.index(identity)
            cycle = (*stack[start:], identity)
            raise LclConfigCycleError(
                "config using cycle: " + " -> ".join(cycle),
                code=ConfigurationErrorCode.E23_CONFIG_USING_CYCLE_JOIN_CYCLE,
            )
        active = (*stack, identity)
        for declaration in loaded.document.declarations:
            if isinstance(declaration, ConfigDefinition):
                output.append(declaration)
                continue
            if not isinstance(declaration, (ConfigUsing, ConfigImport)):
                raise LclValidationError(
                    "unsupported config loading declaration",
                    code=ConfigurationErrorCode.E23_DECLARATION_TYPE,
                )
            target_text: str | None = None
            try:
                target_text = await evaluate_using_target(
                    declaration, output, overrides, namespace_names=frozenset(namespaces)
                )
                target = resolve_using_path(target_text, loaded.source)
                try:
                    child = await self.source_for(target, loaded.source)
                except LclConfigUsingError as error:
                    if declaration.optional and isinstance(error.__cause__, FileNotFoundError):
                        continue
                    raise
                if isinstance(declaration, ConfigImport):
                    isolated: list[ConfigDefinition] = []
                    child_namespaces: set[str] = set()
                    await self.expand(
                        child, active, depth + 1, isolated, overrides, child_namespaces
                    )
                    Config(
                        child.document.version,
                        child.document.origin,
                        tuple(isolated),
                        namespace_names=frozenset(child_namespaces),
                    )
                    qualified, reservations = qualify_import(
                        isolated, child_namespaces, declaration.alias
                    )
                    output.extend(qualified)
                    namespaces.update(reservations)
                else:
                    await self.expand(child, active, depth + 1, output, overrides, namespaces)
            except Exception as error:
                raise derive_loading_error(
                    error, ConfigLoadFrame(loaded.document.origin, declaration.span, target_text)
                ) from error.__cause__
