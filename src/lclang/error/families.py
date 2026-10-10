"""Public exception families for lclang operations."""

from lclang.error.base import LclAttributeError, LclError, LclStateError, LclValidationError
from lclang.error.codes.cli import Code as cli_codes
from lclang.error.codes.configuration import Code as configuration_codes
from lclang.error.codes.language import Code as language_codes
from lclang.error.codes.logging import Code as logging_codes
from lclang.error.codes.runtime import Code as runtime_codes
from lclang.error.codes.standard import Code as standard_codes
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.error.groups import LclErrorGroup


class LclSyntaxError(LclError):
    """Report invalid LCL source syntax.

    .. note::
       The default diagnostic code is ``LCL100000``.
    """

    default_code = str(language_codes.SYNTAX)


class LclNameError(LclError):
    """Report an unresolved LCL variable.

    .. note::
       The default diagnostic code is ``LCL230000``.
    """

    default_code = str(runtime_codes.NAME)


class LclEvaluationError(LclError):
    """Report a failure while evaluating an LCL expression.

    .. note::
       The default diagnostic code is ``LCL130000``.
    """

    default_code = str(language_codes.EVALUATION)


class LclCircularDependencyError(LclEvaluationError):
    """Report a circular variable or function dependency.

    .. note::
       The default diagnostic code is ``LCL243960``.
    """

    default_code = str(runtime_codes.CIRCULAR)


class LclClosedFrameError(LclEvaluationError):
    """Report evaluation attempted through a closed Frame.

    .. note::
       The default diagnostic code is ``LCL236611``.
    """

    default_code = str(runtime_codes.E36_FRAME_IS_CLOSED)


class LclConfigError(LclError):
    """Report invalid configuration content or loading.

    .. note::
       The default diagnostic code is ``LCL300000``.
    """

    default_code = str(configuration_codes.CONFIGURATION)


class LclCliError(LclError):
    """Base class for command-line framework failures.

    .. note::
       The default diagnostic code is ``LCL400000``.
    """

    default_code = str(cli_codes.CLI)


class LclCliUsageError(LclCliError):
    """Report invalid command-line usage.

    .. note::
       The default diagnostic code is ``LCL430000``.
    """

    default_code = str(cli_codes.USAGE)


class LclWorkflowError(LclError):
    """Report a workflow execution failure."""

    default_code = str(workflow_codes.WORKFLOW)


class LclLoggerError(LclError):
    """Report a logger configuration or output failure."""

    default_code = str(logging_codes.LOGGER)


class LclUtilityError(LclError):
    """Report a utility operation failure."""

    default_code = str(utilities_codes.UTILITY)


class LclStandardError(LclError):
    """Report a standard-library operation failure."""

    default_code = str(standard_codes.STANDARD)


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
