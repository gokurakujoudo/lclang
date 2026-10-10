"""Compatibility exports for detached diagnostic records."""

from lclang.error.context import (
    ConfigLoadFrame,
    DiagnosticValue,
    EvaluationContextFrame,
    validate_record_tuple,
)

# Unitless names retain established record imports.
__all__ = ["ConfigLoadFrame", "DiagnosticValue", "EvaluationContextFrame", "validate_record_tuple"]
