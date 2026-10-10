"""Explicit complete-definition requirements for configuration and host inputs.

Defines ``OverrideMarker``.
"""

from enum import Enum


class OverrideMarker(Enum):
    """Identify a lazy, value-less definition reservation.

    .. note::
       These unitless spellings are language declaration markers. Required
       configuration values reject host fallback; runtime reservations allow it.
    """

    # Unitless language spellings distinguish configuration-only replacement
    # from host-supplied runtime values, using enum identity for both policies.
    NEED_OVERRIDE = "NEED_OVERRIDE"
    RUNTIME_OVERRIDE = "RUNTIME_OVERRIDE"

    def __repr__(self) -> str:
        """Return the complete-definition source spelling.

        :returns: Stable language marker text.
        """
        return self.value


# Public identity markers use the enum's singleton members, without runtime state.
NEED_OVERRIDE = OverrideMarker.NEED_OVERRIDE
RUNTIME_OVERRIDE = OverrideMarker.RUNTIME_OVERRIDE
