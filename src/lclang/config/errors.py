"""Structured failures raised by configuration parsing and loading."""

from lclang.errors import LclConfigError


class LclConfigSyntaxError(LclConfigError):
    """Report malformed `.lclcfg` syntax.

    .. note::
       The stable default code is ``LCL4101``.
    """

    default_code = "LCL4101"


class LclConfigVersionError(LclConfigError):
    """Report invalid or unsupported configuration version metadata.

    .. note::
       The stable default code is ``LCL4102``.
    """

    default_code = "LCL4102"


class LclConfigUsingError(LclConfigError):
    """Report failure to resolve or retrieve a `using` target.

    .. note::
       The stable default code is ``LCL4201``.
    """

    default_code = "LCL4201"


class LclConfigCycleError(LclConfigUsingError):
    """Report a recursive `using` expansion cycle.

    .. note::
       The stable default code is ``LCL4202``.
    """

    default_code = "LCL4202"


class LclConfigLimitError(LclConfigError):
    """Report exhaustion of a configured loading limit.

    .. note::
       The stable default code is ``LCL4301``.
    """

    default_code = "LCL4301"


class LclConfigLifecycleError(LclConfigError):
    """Report use of one loader across incompatible event loops.

    .. note::
       The stable default code is ``LCL4302``.
    """

    default_code = "LCL4302"
