"""Public exception families for lclang operations.

Defines ``LclSyntaxError``, ``LclNameError``, ``LclEvaluationError``,
``LclCircularDependencyError``, ``LclClosedFrameError``, ``LclConfigError``,
``LclCliError``, ``LclCliUsageError``, ``LclWorkflowError``, ``LclLoggerError``,
``LclUtilityError``, ``LclStandardError``, ``WorkflowStatusStop``.
"""

from lclang.error.codes.e1_language_error_code import LanguageErrorCode
from lclang.error.codes.e2_runtime_error_code import RuntimeErrorCode
from lclang.error.codes.e3_configuration_error_code import ConfigurationErrorCode
from lclang.error.codes.e4_cli_error_code import CliErrorCode
from lclang.error.codes.e5_workflow_error_code import WorkflowErrorCode
from lclang.error.codes.e6_logger_error_code import LoggerErrorCode
from lclang.error.codes.e7_utility_error_code import UtilityErrorCode
from lclang.error.codes.e9_standard_library_error_code import StandardLibraryErrorCode
from lclang.error.exception_base import (
    LclAttributeError,
    LclError,
    LclStateError,
    LclValidationError,
)
from lclang.error.exception_group import LclErrorGroup


class LclSyntaxError(LclError):
    """Report invalid LCL source syntax.

    .. note::
       The default diagnostic code is ``LCL100000``.
    """

    default_code = str(LanguageErrorCode.E00_SYNTAX)


class LclNameError(LclError):
    """Report an unresolved LCL variable.

    .. note::
       The default diagnostic code is ``LCL230000``.
    """

    default_code = str(RuntimeErrorCode.E30_NAME)


class LclEvaluationError(LclError):
    """Report a failure while evaluating an LCL expression.

    .. note::
       The default diagnostic code is ``LCL130000``.
    """

    default_code = str(LanguageErrorCode.E30_EVALUATION)


class LclCircularDependencyError(LclEvaluationError):
    """Report a circular variable or function dependency.

    .. note::
       The default diagnostic code is ``LCL243960``.
    """

    default_code = str(RuntimeErrorCode.E43_CIRCULAR)


class LclClosedFrameError(LclEvaluationError):
    """Report evaluation attempted through a closed Frame.

    .. note::
       The default diagnostic code is ``LCL236611``.
    """

    default_code = str(RuntimeErrorCode.E36_FRAME_IS_CLOSED)


class LclConfigError(LclError):
    """Report invalid configuration content or loading.

    .. note::
       The default diagnostic code is ``LCL300000``.
    """

    default_code = str(ConfigurationErrorCode.E00_CONFIGURATION)


class LclCliError(LclError):
    """Base class for command-line framework failures.

    .. note::
       The default diagnostic code is ``LCL400000``.
    """

    default_code = str(CliErrorCode.E00_CLI)


class LclCliUsageError(LclCliError):
    """Report invalid command-line usage.

    .. note::
       The default diagnostic code is ``LCL430000``.
    """

    default_code = str(CliErrorCode.E30_USAGE)


class LclWorkflowError(LclError):
    """Report a workflow execution failure."""

    default_code = str(WorkflowErrorCode.E00_WORKFLOW)


class LclLoggerError(LclError):
    """Report a logger configuration or output failure."""

    default_code = str(LoggerErrorCode.E00_LOGGER)


class LclUtilityError(LclError):
    """Report a utility operation failure."""

    default_code = str(UtilityErrorCode.E00_UTILITY)


class LclStandardError(LclError):
    """Report a standard-library operation failure."""

    default_code = str(StandardLibraryErrorCode.E00_STANDARD)


# Unitless export names curate the public exception API without initialization.
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


class WorkflowStatusStop(LclWorkflowError):
    """Carry one synthetic exception for an explicit stopping status."""
