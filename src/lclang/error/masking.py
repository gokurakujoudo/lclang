"""Primitive task-local redaction state shared by errors and diagnostics."""

from contextvars import ContextVar

# Unitless task-local flag starts false; only explicit masking scopes suppress payloads.
ACTIVE_MASKED_VALUE: ContextVar[bool] = ContextVar("lclang_active_masked_value", default=False)
