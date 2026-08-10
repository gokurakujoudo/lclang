"""Version identifiers for the independently versioned LCL grammar."""

from enum import StrEnum


class LanguageVersion(StrEnum):
    """Supported serialized LCL grammar versions.

    .. note::
       Enum values are stable strings suitable for persisted configuration.
    """

    V1 = "1"


LCL_V1 = LanguageVersion.V1
"""Stable default grammar version used when callers omit a version."""
