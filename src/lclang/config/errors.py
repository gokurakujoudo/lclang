"""Compatibility exports for structured failure support."""

from lclang.error.configuration import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    LclConfigVersionError,
)

# Unitless names retain the established module surface.
__all__ = [
    "LclConfigSyntaxError",
    "LclConfigVersionError",
    "LclConfigUsingError",
    "LclConfigCycleError",
    "LclConfigLimitError",
    "LclConfigLifecycleError",
]
