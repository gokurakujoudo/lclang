"""Compatibility exports for structured failure support."""

from lclang.error.loading import (
    derive_loading_error,
)

# Unitless names retain the established module surface.
__all__ = ["derive_loading_error"]
