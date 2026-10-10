"""Immutable expanded configuration result and runtime conversion.

Defines ``Config``, ``validate_config_structure``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from lclang.common.identifiers import ModuleName
from lclang.common.source_location import SourceOrigin
from lclang.config.config_document import ConfigDefinition
from lclang.error import ConfigurationErrorCode, LclConfigError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.common.binding_declaration import real_binding_names
from lclang.lang.common.binding_names import validate_real_conflicts
from lclang.lang.common.namespace_names import (
    validate_namespace_conflicts,
    validate_namespace_names,
)
from lclang.lang.runtime import EvaluationLimits, Frame, FrameFactory, Module, Preset


@guard_constructor(LclValidationError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class Config:
    """Expose one completely expanded immutable configuration snapshot.

    :param version: Root document language version.
    :param root_origin: Root physical source origin.
    :param expanded: Chronological definition occurrences after expansion.
    :param definitions: Computed read-only final-winner mapping.
    :param history: Computed read-only chronological history mapping.
    :param masked_names: Computed immutable sticky exact-name mask policy.
    :param namespace_names: Explicit namespace reservations, including empty imports.

    .. note::
       Reassigning an existing dictionary key preserves first-appearance order.
    """

    version: int
    root_origin: SourceOrigin
    expanded: tuple[ConfigDefinition, ...]
    definitions: Mapping[str, ConfigDefinition] = field(init=False, repr=False)
    history: Mapping[str, tuple[ConfigDefinition, ...]] = field(init=False, repr=False)
    masked_names: frozenset[str] = field(init=False)
    namespace_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)

    @guard_failure(LclValidationError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Detach occurrences and build stable winners and histories.

        :returns: ``None``.

        .. note::
           Shadowing changes the winner without moving its display position.
        """
        expanded = tuple(self.expanded)
        winners: dict[str, ConfigDefinition] = {}
        histories: dict[str, list[ConfigDefinition]] = {}
        for definition in expanded:
            name = str(definition.name)
            winners[name] = definition
            histories.setdefault(name, []).append(definition)
        object.__setattr__(self, "expanded", expanded)
        object.__setattr__(self, "definitions", MappingProxyType(winners))
        object.__setattr__(
            self,
            "masked_names",
            frozenset(str(item.name) for item in expanded if item.masked),
        )
        validate_config_structure(winners, self.namespace_names)
        history = {name: tuple(items) for name, items in histories.items()}
        object.__setattr__(self, "history", MappingProxyType(history))

    @guard_failure(LclConfigError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
    def to_module(self, name: str | None = None) -> Module:
        """Convert final winners into one immutable runtime Module.

        :param name: Optional non-empty runtime module name.
        :returns: Module containing only final winning AST definitions.
        :raises LclValidationError: If an explicit name is empty.

        .. note::
           Conversion performs no evaluation and retains physical AST spans.
        """
        selected = str(self.root_origin.name) if name is None else name
        return Module(
            ModuleName(selected),
            {key: definition.expression for key, definition in self.definitions.items()},
            masked_names=self.masked_names,
            namespace_names=self.namespace_names,
        )

    @guard_failure(LclConfigError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
    def to_frame(self, *, preset: dict[str, object] | None = None) -> Frame:
        """Create a fresh canonical Frame from this configuration.

        :param preset: Optional host bindings copied below configuration definitions.
        :returns: Caller-owned Frame with independent lazy result snapshots.
        :raises LclValidationError: If *preset* is not a dictionary or its keys are not text.
        :raises LclValidationError: If preset binding names or scoped conflicts are invalid.
        """
        from lclang.lang.runtime.module_frame_factory import define_frame

        return define_frame(self.to_module(), preset=preset)

    @guard_failure(LclConfigError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
    def frame_factory(
        self,
        *,
        preset: Preset | None = None,
        parent: Frame | None = None,
        limits: EvaluationLimits | None = None,
    ) -> FrameFactory:
        """Build reusable independent-Frame construction policy.

        :param preset: Optional immutable host bindings.
        :param parent: Optional borrowed parent, or canonical imports by default.
        :param limits: Optional default evaluation limits.
        :returns: Fresh immutable runtime factory.

        .. note::
           Every Frame created by the factory owns independent cache state.
        """
        from lclang.lang.runtime.module_frame_factory import LCL_IMPORTS

        selected_parent = LCL_IMPORTS if parent is None else parent
        return FrameFactory(self.to_module(), preset, limits, selected_parent)


@guard_failure(LclValidationError, ConfigurationErrorCode.E31_CONFIG_COMPOSITION_NATIVE_FAILURE)
def validate_config_structure(
    winners: Mapping[str, ConfigDefinition], namespaces: frozenset[str]
) -> None:
    """Validate final configuration structure and retain the conflicting declaration.

    :param winners: Last chronological definition for each actual binding name.
    :param namespaces: Explicit namespace reservations, including empty imports.
    :raises LclValidationError: If namespace metadata has an unsupported type.
    :raises LclValidationError: If ordinary bindings or namespace reservations conflict.
    """
    validate_namespace_names(namespaces)
    real_names = real_binding_names({key: item.expression for key, item in winners.items()}, {})
    try:
        validate_real_conflicts(real_names)
        validate_namespace_conflicts(namespaces, real_names)
    except LclValidationError as error:
        names = cast(tuple[str, ...], error.__dict__["binding_names"])
        conflicts = [definition for key, definition in winners.items() if key in names]
        vars(error)["source_span"] = conflicts[-1].span
        raise
