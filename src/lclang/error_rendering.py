"""Compatibility exports for structured failure support."""

from lclang.error.rendering import (
    render_error,
    render_failure,
    select_error_action,
)

# Unitless names retain the established module surface.
__all__ = ["render_error", "render_failure", "select_error_action"]
