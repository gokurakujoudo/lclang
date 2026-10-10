"""Structured failures raised by configuration parsing and loading.

Defines ``LclConfigSyntaxError``, ``LclConfigVersionError``, ``LclConfigUsingError``,
``LclConfigCycleError``, ``LclConfigLimitError``, ``LclConfigLifecycleError``.
"""

from lclang.error.codes.e3_configuration_error_code import ConfigurationErrorCode
from lclang.error.exception_family import LclConfigError


class LclConfigSyntaxError(LclConfigError):
    """Report malformed `.lclcfg` syntax."""

    default_code = str(ConfigurationErrorCode.E10_SYNTAX)


class LclConfigVersionError(LclConfigError):
    """Report invalid or unsupported configuration version metadata."""

    default_code = str(ConfigurationErrorCode.E13_VERSION)


class LclConfigUsingError(LclConfigError):
    """Report failure to resolve or retrieve a configuration file target."""

    default_code = str(ConfigurationErrorCode.E20_USING)


class LclConfigCycleError(LclConfigUsingError):
    """Report a recursive configuration file expansion cycle."""

    default_code = str(ConfigurationErrorCode.E23_CYCLE)


class LclConfigLimitError(LclConfigError):
    """Report exhaustion of a configured loading limit."""

    default_code = str(ConfigurationErrorCode.E25_LIMIT)


class LclConfigLifecycleError(LclConfigError):
    """Report use of one loader across incompatible event loops."""

    default_code = str(ConfigurationErrorCode.E23_LIFECYCLE)
