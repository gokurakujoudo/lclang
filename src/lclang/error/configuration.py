"""Structured failures raised by configuration parsing and loading."""

from lclang.error.codes.configuration import Code as configuration_codes
from lclang.error.families import LclConfigError


class LclConfigSyntaxError(LclConfigError):
    """Report malformed `.lclcfg` syntax."""

    default_code = str(configuration_codes.SYNTAX)


class LclConfigVersionError(LclConfigError):
    """Report invalid or unsupported configuration version metadata."""

    default_code = str(configuration_codes.VERSION)


class LclConfigUsingError(LclConfigError):
    """Report failure to resolve or retrieve a configuration file target."""

    default_code = str(configuration_codes.USING)


class LclConfigCycleError(LclConfigUsingError):
    """Report a recursive configuration file expansion cycle."""

    default_code = str(configuration_codes.CYCLE)


class LclConfigLimitError(LclConfigError):
    """Report exhaustion of a configured loading limit."""

    default_code = str(configuration_codes.LIMIT)


class LclConfigLifecycleError(LclConfigError):
    """Report use of one loader across incompatible event loops."""

    default_code = str(configuration_codes.LIFECYCLE)
