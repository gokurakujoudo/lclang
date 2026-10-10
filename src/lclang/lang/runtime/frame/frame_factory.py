"""Reusable immutable policy for constructing independent runtime Frames.

Defines ``FrameFactory``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

if TYPE_CHECKING:
    from lclang.lang.runtime.frame.frame import Frame

from collections.abc import Mapping
from dataclasses import dataclass

from lclang.common.binding_mask import normalize_masked_mapping
from lclang.common.identifiers import FrameId
from lclang.lang.runtime.frame.evaluation_limit import EvaluationLimits
from lclang.lang.runtime.frame.frame import Frame
from lclang.lang.runtime.module import Module
from lclang.lang.runtime.preset import Preset


@guard_constructor(LclValidationError, RuntimeErrorCode.E39_FRAME_FACTORY_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class FrameFactory:
    """Retain immutable policy for creating independent Frames.

    :param module: Immutable definitions used by every created Frame.
    :param preset: Optional reusable base host bindings.
    :param limits: Optional default evaluation limits.
    :param parent: Optional borrowed default parent for every created Frame.
    :raises LclValidationError: If any policy field has the wrong public type.

    .. note::
       Construction creates no Frame, cache, task, trace, or owned resource.
    """

    module: Module
    preset: Preset | None = None
    limits: EvaluationLimits | None = None
    parent: Frame | None = None

    @guard_failure(LclValidationError, RuntimeErrorCode.E39_FRAME_FACTORY_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Reject invalid policy objects before any Frame is created.

        :returns: ``None`` after successful policy validation.
        :raises LclValidationError: If module, preset, limits, or parent has a wrong type.

        .. note::
           Parent validation borrows the Frame without inspecting its lifecycle.
        """
        if not isinstance(self.module, Module):
            raise LclValidationError(
                "FrameFactory module must be a Module",
                code=RuntimeErrorCode.E39_FRAMEFACTORY_MODULE_MUST_BE_A_MODULE,
            )
        if self.preset is not None and not isinstance(self.preset, Preset):
            raise LclValidationError(
                "FrameFactory preset must be a Preset",
                code=RuntimeErrorCode.E39_FRAMEFACTORY_PRESET_MUST_BE_A_PRESET,
            )
        if self.limits is not None and not isinstance(self.limits, EvaluationLimits):
            raise LclValidationError(
                "FrameFactory limits must be EvaluationLimits",
                code=RuntimeErrorCode.E39_FRAMEFACTORY_LIMITS_MUST_BE_EVALUATIONLIMITS,
            )
        if self.parent is not None and not isinstance(self.parent, Frame):
            raise LclValidationError(
                "FrameFactory parent must be a Frame",
                code=RuntimeErrorCode.E39_FRAMEFACTORY_PARENT_MUST_BE_A_FRAME,
            )

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E39_FRAME_FACTORY_NATIVE_FAILURE)
    def with_preset(self, preset: Preset) -> FrameFactory:
        """Return new policy with one right-biased preset overlay.

        :param preset: Immutable bindings to add or replace.
        :returns: New factory retaining the same module and limits.
        :raises LclValidationError: If *preset* is not a Preset.

        .. note::
           With no existing preset, the supplied preset is retained directly.
        """
        if not isinstance(preset, Preset):
            raise LclValidationError(
                "FrameFactory preset must be a Preset",
                code=RuntimeErrorCode.E39_FRAMEFACTORY_PRESET_MUST_BE_A_PRESET,
            )
        combined = preset if self.preset is None else self.preset.overlay(preset)
        return FrameFactory(self.module, combined, self.limits, self.parent)

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E39_FRAME_FACTORY_NATIVE_FAILURE)
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
        :raises LclValidationError: If the frame or a binding name is empty.
        :raises LclValidationError: If call-level parent or limits have the wrong type.

        .. note::
           Each call owns fresh caches, tasks, traces, and lifecycle state.
        """
        if limits is not None and not isinstance(limits, EvaluationLimits):
            raise LclValidationError(
                "Frame limits must be EvaluationLimits",
                code=RuntimeErrorCode.E39_FRAME_LIMITS_MUST_BE_EVALUATIONLIMITS,
            )
        if parent is not None and not isinstance(parent, Frame):
            raise LclValidationError(
                "Frame parent must be a Frame",
                code=RuntimeErrorCode.E39_FRAME_PARENT_MUST_BE_A_FRAME,
            )
        bindings = {} if self.preset is None else dict(self.preset.values)
        masked_names = frozenset[str]() if self.preset is None else self.preset.masked_names
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
