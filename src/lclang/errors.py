"""Compatibility exports for the public exception families."""

from lclang.error import (
    LclAttributeError,
    LclCircularDependencyError,
    LclCliError,
    LclCliUsageError,
    LclClosedFrameError,
    LclConfigError,
    LclError,
    LclErrorGroup,
    LclEvaluationError,
    LclLoggerError,
    LclNameError,
    LclStandardError,
    LclStateError,
    LclSyntaxError,
    LclUtilityError,
    LclValidationError,
    LclWorkflowError,
)

# Unitless names retain the established exception import surface.
__all__ = [
    "LclError",
    "LclErrorGroup",
    "LclValidationError",
    "LclStateError",
    "LclAttributeError",
    "LclSyntaxError",
    "LclNameError",
    "LclEvaluationError",
    "LclCircularDependencyError",
    "LclClosedFrameError",
    "LclConfigError",
    "LclCliError",
    "LclCliUsageError",
    "LclWorkflowError",
    "LclLoggerError",
    "LclUtilityError",
    "LclStandardError",
]
