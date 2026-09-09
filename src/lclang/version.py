"""Version identifiers for the independently versioned LCL grammar."""

from enum import StrEnum


class LanguageVersion(StrEnum):
    """Supported serialized LCL grammar versions.

    .. note::
       Enum values are stable strings suitable for persisted configuration.
    """

    # Unitless version label comes from the supported language contract; the sole value
    # identifies stable version 1 semantics.
    # Unitless language version values below come from the stable V1 contract. The explicit
    # alias selects the sole supported semantics without requiring callers to construct a
    # version value.
    V1 = "1"


LCL_V1 = LanguageVersion.V1
"""Stable default grammar version used when callers omit a version."""
