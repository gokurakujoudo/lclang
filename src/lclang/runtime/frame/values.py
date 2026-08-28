"""Controlled updates for Frame host-value bindings."""

from __future__ import annotations

from typing import Protocol, cast

from lclang.masking import normalize_masked_mapping
from lclang.runtime.frame.scoped import validate_mixin_tree
from lclang.scopes import validate_binding_names
from lclang.source import SourceSpan


class LifecycleAccess(Protocol):
    """Describe the lifecycle guard required by value updates.

    .. note::
       The concrete lifecycle retains ownership of closing-state diagnostics.
    """

    def ensure_open(self, span: SourceSpan | None) -> None:
        """Reject work after Frame closing begins.

        :param span: Optional source span for structured diagnostics.
        :returns: ``None`` when the Frame remains open.

        .. note::
           Host-side mixin calls supply no semantic source span.
        """
        ...


class MutableFrameValues(Protocol):
    """Describe mutable state privately owned by a concrete Frame.

    :param values: Public read-only view of current host bindings.
    :param masked_names: Immutable current local exact-name mask policy.

    .. note::
       Public callers continue to receive only the read-only values view.
    """

    _values: dict[str, object]
    _lifecycle: LifecycleAccess
    values: object
    masked_names: frozenset[str]


class FrameValuesApi:
    """Provide controlled right-biased Frame host-value updates.

    .. note::
       Mixing values never invalidates definition result or failure snapshots.
    """

    def mixin(self, values: dict[str, object]) -> None:
        """Copy host bindings into an open Frame.

        :param values: String-keyed host bindings applied right-biased.
        :returns: ``None`` after the atomic mapping update.
        :raises TypeError: If *values* is not a string-keyed dictionary.
        :raises ValueError: If a host-binding name is empty.
        :raises LclClosedFrameError: If Frame closing has begun.

        .. note::
           Validation and detachment finish before any owned state is changed.
        """
        if not isinstance(values, dict):
            raise TypeError("Frame mixin values must be a dictionary")
        if any(not isinstance(name, str) for name in values):
            raise TypeError("Frame mixin names must be strings")
        updates, masked_names = normalize_masked_mapping(values)
        if any(not name for name in updates):
            raise ValueError("host binding name cannot be empty")
        validate_binding_names(updates)
        frame = cast(MutableFrameValues, self)
        frame._lifecycle.ensure_open(None)
        prospective = dict(cast(dict[str, object], frame.values))
        prospective.update(updates)
        validate_mixin_tree(frame, prospective)
        frame._values.update(updates)
        frame.masked_names = frozenset(frame.masked_names | masked_names)
