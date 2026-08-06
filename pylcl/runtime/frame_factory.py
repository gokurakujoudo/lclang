"""Reusable immutable policy for constructing independent runtime Frames."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pylcl.runtime.frames import Frame
from pylcl.runtime.limits import EvaluationLimits
from pylcl.runtime.modules import Module
from pylcl.runtime.presets import Preset
from pylcl.types import FrameId


@dataclass(frozen=True, slots=True)
class FrameFactory:
    """Retain immutable policy for creating independent Frames.

    :param module: Immutable definitions used by every created Frame.
    :param preset: Optional reusable base host bindings.
    :param limits: Optional default evaluation limits.
    :raises TypeError: If any policy field has the wrong public type.

    .. note::
       Construction creates no Frame, cache, task, trace, or owned resource.
    """

    module: Module
    preset: Preset | None = None
    limits: EvaluationLimits | None = None

    def __post_init__(self) -> None:
        """Reject invalid policy objects before any Frame is created."""
        if not isinstance(self.module, Module):
            raise TypeError("FrameFactory module must be a Module")
        if self.preset is not None and not isinstance(self.preset, Preset):
            raise TypeError("FrameFactory preset must be a Preset")
        if self.limits is not None and not isinstance(self.limits, EvaluationLimits):
            raise TypeError("FrameFactory limits must be EvaluationLimits")

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
        return FrameFactory(self.module, combined, self.limits)

    def create(
        self,
        frame_id: FrameId,
        *,
        values: Mapping[str, object] | None = None,
        parent: Frame | None = None,
        limits: EvaluationLimits | None = None,
    ) -> Frame:
        """Create one independent Frame from effective override policy.

        :param frame_id: Non-empty identifier for the new runtime instance.
        :param values: Optional call-level bindings overriding the preset.
        :param parent: Optional borrowed parent Frame.
        :param limits: Optional call-level limits overriding factory defaults.
        :returns: A fresh Frame with no shared mutable runtime state.
        :raises ValueError: If the frame or a binding name is empty.
        :raises TypeError: If call-level limits have the wrong public type.

        .. note::
           Each call owns fresh caches, tasks, traces, and lifecycle state.
        """
        if limits is not None and not isinstance(limits, EvaluationLimits):
            raise TypeError("Frame limits must be EvaluationLimits")
        bindings = {} if self.preset is None else dict(self.preset.values)
        if values is not None:
            bindings.update(values)
        effective_limits = self.limits if limits is None else limits
        return Frame(
            self.module,
            frame_id,
            values=bindings,
            parent=parent,
            limits=effective_limits,
        )
