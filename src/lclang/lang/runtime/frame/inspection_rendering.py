"""Text rendering for detached Frame inspection values.

Defines ``render_inspection``, ``canonical_value_repr``, ``native_value_payload``,
``compact_repr``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.utils.value_representation import safe_repr

if TYPE_CHECKING:
    pass
from typing import TYPE_CHECKING

from lclang.common.binding_mask import MASKED_VALUE
from lclang.common.scoped_proxy import ScopedProxyFactory
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.printer import to_source
from lclang.lang.runtime.frame.variable_inspection import (
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.lang.stdlib.recursive_function import RecursiveFunction
from lclang.lang.stdlib.stdlib_namespace import StdlibNamespace


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def render_inspection(self: VariableInspectionTree) -> str:
    """Return a compact non-recursive single-line summary.

    :param self: Inspection node to render without evaluating it.
    :returns: Stable summary excluding recursive AST, Frame, and child details.

    .. note::
       Values use their escaped representation; failures use their escaped
       message so the output remains one physical line.
    """
    path = "/".join(str(frame_id) for frame_id in self.definition_path)
    if self.masked:
        return f"{self.var_name}@{path}: ({self.status.value}) {MASKED_VALUE}"
    if self.definition is None:
        definition = (
            ""
            if self.status
            in {
                VariableInspectionStatus.EXTERNAL_PROVIDED,
                VariableInspectionStatus.NATIVE_PROVIDED,
                VariableInspectionStatus.FRAME_PROXY,
            }
            else "<missing> "
        )
    else:
        definition = f"{to_source(self.definition)} "
    if self.current_exception is not None:
        payload = (
            f"{type(self.current_exception).__name__}: "
            f"{safe_repr(self.current_exception, renderer=str, max_length=None)}"
        )
    elif isinstance(self.current_value, RecursiveFunction):
        payload = compact_repr(self.current_value)
    else:
        payload = (
            native_value_payload(str(self.var_name), self.current_value)
            if self.status is VariableInspectionStatus.NATIVE_PROVIDED
            else (f"{type(self.current_value).__name__}: {compact_repr(self.current_value)}")
        )
    return f"{self.var_name}@{path}: {definition}({self.status.value}) {payload}"


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def canonical_value_repr(value: object) -> str:
    """Return one physical line for an arbitrary current value.

    :param value: Opaque cached value, host object, or exception.
    :returns: Canonical LCL source for supported AST values, otherwise repr.

    .. note::
       Unsupported custom AST nodes retain ordinary repr; all output is one line.
    """
    if isinstance(value, LclAstNode):
        try:
            return to_source(value)
        except TypeError, LclValidationError:
            pass
    return repr(value)


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def native_value_payload(name: str, value: object) -> str:
    """Return the uniform dependency-tree payload for a canonical native value.

    :param name: Selected binding name used for callable diagnostics.
    :param value: Reviewed lclang value retained by a canonical Frame.
    :returns: Builtin function/namespace grammar or a typed fallback payload.
    """
    if isinstance(value, StdlibNamespace):
        return f"Builtin Namespace: {value.namespace}"
    if isinstance(value, ScopedProxyFactory):
        return f"Builtin Utility: {name}"
    if callable(value):
        return f"Builtin Function: {name}"
    return f"{type(value).__name__}: {compact_repr(value)}"


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def compact_repr(value: object) -> str:
    """Render canonical values safely without truncating inspection output.

    :param value: Current cached or host value.
    :returns: Protected single-line canonical AST or ordinary representation.
    """
    return safe_repr(value, renderer=canonical_value_repr, max_length=None)
