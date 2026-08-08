"""Controlled updates for Frame host-value bindings."""

from __future__ import annotations

from typing import Protocol, cast

from pylcl.source import SourceSpan


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

    .. note::
       Public callers continue to receive only the read-only values view.
    """

    _values: dict[str, object]
    _lifecycle: LifecycleAccess


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
        updates = dict(values)
        if any(not isinstance(name, str) for name in updates):
            raise TypeError("Frame mixin names must be strings")
        if any(not name for name in updates):
            raise ValueError("host binding name cannot be empty")
        frame = cast(MutableFrameValues, self)
        frame._lifecycle.ensure_open(None)
        frame._values.update(updates)
