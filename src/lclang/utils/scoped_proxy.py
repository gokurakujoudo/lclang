"""Shared scoped-proxy protocols.

Defines ``ScopedProxyValue``, ``ScopedProxyFactory``, ``scoped_proxy_factory``.
"""

from __future__ import annotations

from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure


class ScopedProxyValue:
    """Mark a caller-bound scoped value with custom attribute resolution."""


class ScopedProxyFactory:
    """Mark a utility that creates caller-bound scoped values."""


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def scoped_proxy_factory(value: object) -> ScopedProxyFactory | None:
    """Return a scoped utility factory carried by a host or constant value.

    :param value: Candidate semantic or host value.
    :returns: Factory instance, or ``None`` for an ordinary value.
    """
    return value if isinstance(value, ScopedProxyFactory) else None
