"""Public structured errors, diagnostic records, and failure groups."""

from lclang.error.base import (
    LclAttributeError,
    LclError,
    LclFrozenAttributeError,
    LclStateError,
    LclValidationError,
)
from lclang.error.calendar import (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
from lclang.error.codes.catalog import get_error_code_path, get_error_codes
from lclang.error.configuration import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    LclConfigVersionError,
)
from lclang.error.context import ConfigLoadFrame, DiagnosticValue, EvaluationContextFrame
from lclang.error.families import (
    LclCircularDependencyError,
    LclCliError,
    LclCliUsageError,
    LclClosedFrameError,
    LclConfigError,
    LclEvaluationError,
    LclLoggerError,
    LclNameError,
    LclStandardError,
    LclSyntaxError,
    LclUtilityError,
    LclWorkflowError,
)
from lclang.error.groups import LclErrorGroup

# Unitless names curate the diagnostic API without behavioral initialization.
__all__ = [
    "get_error_codes",
    "get_error_code_path",
    "LclFrozenAttributeError",
    "CalendarCannotLoadException",
    "CalendarLogicException",
    "DateOperationOutOfScopeException",
    "UnappliedCalendarOperationException",
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
    "LclConfigCycleError",
    "LclConfigLifecycleError",
    "LclConfigLimitError",
    "LclConfigSyntaxError",
    "LclConfigUsingError",
    "LclConfigVersionError",
    "LclCliError",
    "LclCliUsageError",
    "LclWorkflowError",
    "LclLoggerError",
    "LclUtilityError",
    "LclStandardError",
    "ConfigLoadFrame",
    "DiagnosticValue",
    "EvaluationContextFrame",
]
