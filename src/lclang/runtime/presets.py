"""Immutable named host-binding presets and shallow overlays."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from lclang.error import LclEvaluationError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.runtime import Code as runtime_codes
from lclang.masking import normalize_masked_mapping
from lclang.scopes import real_binding_names, validate_binding_names, validate_real_conflicts


@guard_constructor(LclValidationError, runtime_codes.NATIVE_221)
@dataclass(frozen=True, slots=True)
class Preset:
    """Describe one reusable immutable host-binding snapshot.

    :param name: Non-empty human-readable preset name.
    :param values: String-keyed host bindings copied at construction time.
    :param masked_names: Additional normalized binding names to redact.
    :raises LclValidationError: If the preset or any binding name is empty.

    .. note::
       Values are retained by reference and overlays are deliberately shallow.
    """

    name: str
    values: Mapping[str, object]
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)

    @guard_failure(LclValidationError, runtime_codes.NATIVE_221)
    def __post_init__(self) -> None:
        """Validate names and detach the mapping from caller mutation.

        :raises LclValidationError: If the preset or a binding name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "preset name cannot be empty", code=runtime_codes.E21_PRESET_NAME_CANNOT_BE_EMPTY
            )
        snapshot, masked_names = normalize_masked_mapping(self.values, self.masked_names)
        if any(not name for name in snapshot):
            raise LclValidationError(
                "preset binding name cannot be empty",
                code=runtime_codes.E21_PRESET_NAME_CANNOT_BE_EMPTY,
            )
        validate_binding_names(snapshot)
        validate_real_conflicts(real_binding_names({}, snapshot))
        object.__setattr__(self, "values", MappingProxyType(snapshot))
        object.__setattr__(self, "masked_names", masked_names)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_221)
    def overlay(self, other: Preset, *, name: str | None = None) -> Preset:
        """Return a right-biased shallow overlay of two presets.

        :param other: Preset whose bindings win on collisions.
        :param name: Optional non-empty result name.
        :returns: A detached immutable combined preset.
        :raises LclValidationError: If *other* is not a Preset.
        :raises LclValidationError: If an explicit *name* is empty.

        .. note::
           Neither input mapping nor any mapped value is mutated or awaited.
        """
        if not isinstance(other, Preset):
            raise LclValidationError(
                "preset overlay requires another Preset",
                code=runtime_codes.E21_PRESET_OVERLAY_REQUIRES_ANOTHER_PRESET,
            )
        if name == "":
            raise LclValidationError(
                "preset name cannot be empty", code=runtime_codes.E21_PRESET_NAME_CANNOT_BE_EMPTY
            )
        result_name = f"{self.name}+{other.name}" if name is None else name
        combined = dict(self.values)
        combined.update(other.values)
        return Preset(
            result_name,
            combined,
            masked_names=self.masked_names | other.masked_names,
        )
