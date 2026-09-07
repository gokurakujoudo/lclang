"""Reusable immutable policy for constructing independent runtime Frames."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame

from collections.abc import Mapping
from dataclasses import dataclass

from lclang.masking import normalize_masked_mapping
from lclang.runtime.frame.evaluation_limits import EvaluationLimits
from lclang.runtime.frame.frame import Frame
from lclang.runtime.modules import Module
from lclang.runtime.presets import Preset
from lclang.types import FrameId


@dataclass(frozen=True, slots=True)
class FrameFactory:
    """Retain immutable policy for creating independent Frames.

    :param module: Immutable definitions used by every created Frame.
    :param preset: Optional reusable base host bindings.
    :param limits: Optional default evaluation limits.
    :param parent: Optional borrowed default parent for every created Frame.
    :raises TypeError: If any policy field has the wrong public type.

    .. note::
       Construction creates no Frame, cache, task, trace, or owned resource.
    """

    module: Module
    preset: Preset | None = None
    limits: EvaluationLimits | None = None
    parent: Frame | None = None

    def __post_init__(self) -> None:
        """Reject invalid policy objects before any Frame is created.

        :returns: ``None`` after successful policy validation.
        :raises TypeError: If module, preset, limits, or parent has a wrong type.

        .. note::
           Parent validation borrows the Frame without inspecting its lifecycle.
        """
        if not isinstance(self.module, Module):
            raise TypeError("FrameFactory module must be a Module")
        if self.preset is not None and not isinstance(self.preset, Preset):
            raise TypeError("FrameFactory preset must be a Preset")
        if self.limits is not None and not isinstance(self.limits, EvaluationLimits):
            raise TypeError("FrameFactory limits must be EvaluationLimits")
        if self.parent is not None and not isinstance(self.parent, Frame):
            raise TypeError("FrameFactory parent must be a Frame")

    def with_preset(self, preset: Preset) -> FrameFactory:
        """Return new policy with one right-biased preset overlay.

        :param preset: Immutable bindings to add or replace.
        :returns: New factory retaining the same module and limits.
        :raises TypeError: If *preset* is not a Preset.

        .. note::
           With no existing preset, the supplied preset is retained directly.
        """
        if not isinstance(preset, Preset):
            raise TypeError("FrameFactory preset must be a Preset")
        combined = preset if self.preset is None else self.preset.overlay(preset)
        return FrameFactory(self.module, combined, self.limits, self.parent)

    def create(
        self,
        frame_id: FrameId | str | None = None,
        *,
        values: Mapping[str, object] | None = None,
        parent: Frame | None = None,
        limits: EvaluationLimits | None = None,
    ) -> Frame:
        """Create one independent Frame from effective override policy.

        :param frame_id: Optional identifier; defaults to ``frame-<module name>``.
        :param values: Optional call-level bindings overriding the preset.
        :param parent: Optional borrowed parent overriding factory policy.
        :param limits: Optional call-level limits overriding factory defaults.
        :returns: A fresh Frame with no shared mutable runtime state.
        :raises ValueError: If the frame or a binding name is empty.
        :raises TypeError: If call-level parent or limits have the wrong type.

        .. note::
           Each call owns fresh caches, tasks, traces, and lifecycle state.
        """
        if limits is not None and not isinstance(limits, EvaluationLimits):
            raise TypeError("Frame limits must be EvaluationLimits")
        if parent is not None and not isinstance(parent, Frame):
            raise TypeError("Frame parent must be a Frame")
        bindings = {} if self.preset is None else dict(self.preset.values)
        masked_names = frozenset() if self.preset is None else self.preset.masked_names
        if values is not None:
            updates, update_masks = normalize_masked_mapping(values)
            bindings.update(updates)
            masked_names |= update_masks
        effective_limits = self.limits if limits is None else limits
        effective_parent = self.parent if parent is None else parent
        return Frame(
            self.module,
            frame_id,
            values=bindings,
            parent=effective_parent,
            limits=effective_limits,
            masked_names=masked_names,
        )
