"""AST and host binding declaration recognition.

Defines ``is_frame_proxy``, ``real_binding_names``, ``get_override_marker``.
"""

from __future__ import annotations

from collections.abc import Mapping

from lclang.common.scoped_proxy import scoped_proxy_factory
from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.lang.common.frame_proxy_marker import FRAME_PROXY
from lclang.lang.common.override_marker import OverrideMarker


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def is_frame_proxy(value: object) -> bool:
    """Report whether a value is the public proxy declaration singleton.

    :param value: Candidate AST or host value.
    :returns: Whether *value* declares a Frame proxy.
    """
    from lclang.lang.ast import LclConstant

    return value is FRAME_PROXY or (isinstance(value, LclConstant) and value.value is FRAME_PROXY)


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def real_binding_names(
    definitions: Mapping[str, object],
    values: Mapping[str, object],
) -> tuple[str, ...]:
    """Return real local names after definition precedence.

    :param definitions: Local semantic definitions.
    :param values: Local host values.
    :returns: Real names in stable definition-then-value order.
    """
    result = [
        name
        for name, node in definitions.items()
        if not is_frame_proxy(node) and scoped_proxy_factory(node) is None
    ]
    result.extend(
        name
        for name, value in values.items()
        if name not in definitions
        and not is_frame_proxy(value)
        and scoped_proxy_factory(value) is None
    )
    return tuple(result)


@guard_failure(LclValidationError, DataModelErrorCode.E41_BINDING_NAME_VALIDATION_NATIVE_FAILURE)
def get_override_marker(value: object) -> OverrideMarker | None:
    """Extract a declaration marker from a host value or constant AST.

    :param value: Candidate host value or semantic expression.
    :returns: Marker singleton, or ``None`` for an ordinary value.
    """
    from lclang.lang.ast import LclConstant

    selected = value.value if isinstance(value, LclConstant) else value
    return selected if isinstance(selected, OverrideMarker) else None
