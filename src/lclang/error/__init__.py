"""Public structured errors, diagnostic records, and failure groups.

Exports ``EscapeDecodeError``, ``InternalLiteralScanError``, ``FStringScanError``,
``RouteFailure``, ``WorkflowStatusStop``, ``GeneralErrorCode``, ``LanguageErrorCode``,
``RuntimeErrorCode``, ``ConfigurationErrorCode``, ``CliErrorCode``, ``WorkflowErrorCode``,
``LoggerErrorCode``, ``UtilityErrorCode``, ``DataModelErrorCode``,
``StandardLibraryErrorCode``, ``render_error``, ``render_failure``, ``get_error_codes``,
``get_error_code_path``, ``LclFrozenAttributeError``, ``CalendarCannotLoadException``,
``CalendarLogicException``, ``DateOperationOutOfScopeException``,
``UnappliedCalendarOperationException``, ``LclError``, ``LclErrorGroup``,
``LclValidationError``, ``LclStateError``, ``LclAttributeError``, ``LclSyntaxError``,
``LclNameError``, ``LclEvaluationError``, ``LclCircularDependencyError``,
``LclClosedFrameError``, ``LclConfigError``, ``LclConfigCycleError``,
``LclConfigLifecycleError``, ``LclConfigLimitError``, ``LclConfigSyntaxError``,
``LclConfigUsingError``, ``LclConfigVersionError``, ``LclCliError``, ``LclCliUsageError``,
``LclWorkflowError``, ``LclLoggerError``, ``LclUtilityError``, ``LclStandardError``,
``ConfigLoadFrame``, ``DiagnosticValue``, ``EvaluationContextFrame``.
"""

from lclang.error.calendar_exception import (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
from lclang.error.cli_exception import RouteFailure
from lclang.error.codes.code_registry import get_error_code_path, get_error_codes
from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.codes.e1_language_error_code import LanguageErrorCode
from lclang.error.codes.e2_runtime_error_code import RuntimeErrorCode
from lclang.error.codes.e3_configuration_error_code import ConfigurationErrorCode
from lclang.error.codes.e4_cli_error_code import CliErrorCode
from lclang.error.codes.e5_workflow_error_code import WorkflowErrorCode
from lclang.error.codes.e6_logger_error_code import LoggerErrorCode
from lclang.error.codes.e7_utility_error_code import UtilityErrorCode
from lclang.error.codes.e8_data_model_error_code import DataModelErrorCode
from lclang.error.codes.e9_standard_library_error_code import StandardLibraryErrorCode
from lclang.error.configuration_exception import (
    LclConfigCycleError,
    LclConfigLifecycleError,
    LclConfigLimitError,
    LclConfigSyntaxError,
    LclConfigUsingError,
    LclConfigVersionError,
)
from lclang.error.diagnostic_records import ConfigLoadFrame, DiagnosticValue, EvaluationContextFrame
from lclang.error.diagnostic_rendering import render_error, render_failure
from lclang.error.exception_base import (
    LclAttributeError,
    LclError,
    LclFrozenAttributeError,
    LclStateError,
    LclValidationError,
)
from lclang.error.exception_family import (
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
    WorkflowStatusStop,
)
from lclang.error.exception_group import LclErrorGroup
from lclang.error.lexer_exception import (
    EscapeDecodeError,
    FStringScanError,
    InternalLiteralScanError,
)

# Unitless names curate the diagnostic API without behavioral initialization.
__all__ = [
    "EscapeDecodeError",
    "InternalLiteralScanError",
    "FStringScanError",
    "RouteFailure",
    "WorkflowStatusStop",
    "GeneralErrorCode",
    "LanguageErrorCode",
    "RuntimeErrorCode",
    "ConfigurationErrorCode",
    "CliErrorCode",
    "WorkflowErrorCode",
    "LoggerErrorCode",
    "UtilityErrorCode",
    "DataModelErrorCode",
    "StandardLibraryErrorCode",
    "render_error",
    "render_failure",
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
