"""Immutable expanded configuration result and runtime conversion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pylcl.config.model import ConfigDefinition
from pylcl.runtime import EvaluationLimits, Frame, FrameFactory, Module, Preset
from pylcl.source import SourceOrigin
from pylcl.types import ModuleName


@dataclass(frozen=True, slots=True)
class Config:
    """Expose one completely expanded immutable configuration snapshot.

    :param version: Root document language version.
    :param root_origin: Root physical source origin.
    :param expanded: Chronological definition occurrences after expansion.
    :param definitions: Computed read-only final-winner mapping.
    :param history: Computed read-only chronological history mapping.

    .. note::
       Reassigning an existing dictionary key preserves first-appearance order.
    """

    version: int
    root_origin: SourceOrigin
    expanded: tuple[ConfigDefinition, ...]
    definitions: Mapping[str, ConfigDefinition] = field(init=False, repr=False)
    history: Mapping[str, tuple[ConfigDefinition, ...]] = field(init=False, repr=False)

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
        history = {name: tuple(items) for name, items in histories.items()}
        object.__setattr__(self, "history", MappingProxyType(history))

    def to_module(self, name: str | None = None) -> Module:
        """Convert final winners into one immutable runtime Module.

        :param name: Optional non-empty runtime module name.
        :returns: Module containing only final winning AST definitions.
        :raises ValueError: If an explicit name is empty.

        .. note::
           Conversion performs no evaluation and retains physical AST spans.
        """
        selected = str(self.root_origin.name) if name is None else name
        return Module(
            ModuleName(selected),
            {key: definition.expression for key, definition in self.definitions.items()},
        )

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
        from pylcl.api import LCL_IMPORTS

        selected_parent = LCL_IMPORTS if parent is None else parent
        return FrameFactory(self.to_module(), preset, limits, selected_parent)
