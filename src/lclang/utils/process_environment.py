"""Live read-only process environment without language dependencies.

Defines ``Environment`` and the shared ``env`` view.
"""

from __future__ import annotations

import os

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclAttributeError, LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.utils.scoped_proxy import ScopedProxyFactory


class Environment(ScopedProxyFactory):
    """Expose current process environment variables without mutation."""

    @guard_failure(LclAttributeError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def __getattr__(self, name: str) -> str | None:
        """Return one live environment value through attribute syntax.

        :param name: Environment variable name.
        :returns: Current text value, or ``None`` when absent.
        :raises LclAttributeError: If Python requests a private protocol attribute.
        """
        if name.startswith("__"):
            raise LclAttributeError(name, code=UtilityErrorCode.E31_PRIVATE_ATTRIBUTE_ACCESS)
        return os.environ.get(name)

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def get(self, name: str, default: object = None) -> object:
        """Return one live environment value or a caller-supplied default.

        :param name: Environment variable name, including non-LCL identifiers.
        :param default: Value returned unchanged when the variable is absent.
        :returns: Current text value or *default*.
        :raises LclValidationError: If *name* is not text.
        """
        if not isinstance(name, str):
            raise LclValidationError(
                "environment variable name must be text",
                code=UtilityErrorCode.E31_ENVIRONMENT_VARIABLE_NAME_MUST_BE_TEXT,
            )
        return os.environ.get(name, default)

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def field_names(self) -> list[str]:
        """Return current environment names usable through Python attributes.

        :returns: Alphabetically sorted Unicode identifiers; language keywords are included.
        """
        return sorted(name for name in os.environ if name.isidentifier())


# Shared stateless live environment view.
env = Environment()
