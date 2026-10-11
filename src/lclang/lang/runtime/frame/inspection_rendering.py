"""Text rendering for detached Frame inspection values.

Defines ``render_inspection``, ``canonical_value_repr``, ``native_value_payload``,
``compact_repr``, ``build_inspection_display``.
"""

from __future__ import annotations

from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.failure_summary import render_failure_summary
from lclang.error.operation_guard import guard_failure
from lclang.error.source_excerpt import render_definition_location
from lclang.lang.engine.evaluator.display_capture import render_canonical_value
from lclang.lang.runtime.frame.variable_inspection import (
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.lang.stdlib.recursive_function import RecursiveFunction
from lclang.lang.stdlib.stdlib_namespace import StdlibNamespace
from lclang.utils.binding_mask import MASKED_VALUE
from lclang.utils.scoped_proxy import ScopedProxyFactory
from lclang.utils.text_tree import TextTree, sort_display_name
from lclang.utils.value_representation import safe_repr


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def render_inspection(self: VariableInspectionTree) -> str:
    """Return a compact non-recursive single-line summary.

    :param self: Inspection node to render without evaluating it.
    :returns: Stable summary excluding recursive AST, Frame, and child details.

    .. note::
       Values use their escaped representation; failures use their escaped
       message so the output remains one physical line.
    """
    source = {
        VariableInspectionStatus.CACHED: "cached",
        VariableInspectionStatus.EXTERNAL_PROVIDED: "external",
        VariableInspectionStatus.NATIVE_PROVIDED: "native",
        VariableInspectionStatus.FRAME_PROXY: "proxy",
        VariableInspectionStatus.NOT_EVALUATED: "not evaluated",
    }[self.status]
    if self.masked:
        return f"{self.var_name}: {MASKED_VALUE} ({source})"
    if self.current_exception is not None:
        payload = render_failure_summary(self.current_exception)
    elif self.status is VariableInspectionStatus.NOT_EVALUATED and self.definition is not None:
        expression = safe_repr(self.definition, renderer=canonical_value_repr, max_length=None)
        return (
            f"{self.var_name}: {expression} ({render_definition_location(self.definition.span)}; "
            f"not evaluated; {type(self.definition).__name__})"
        )
    elif isinstance(self.current_value, RecursiveFunction):
        payload = compact_repr(self.current_value)
    else:
        payload = (
            native_value_payload(str(self.var_name), self.current_value)
            if self.status is VariableInspectionStatus.NATIVE_PROVIDED
            else (f"({type(self.current_value).__name__}) {compact_repr(self.current_value)}")
        )
    return f"{self.var_name}: {payload} ({source})"


def build_inspection_display(tree: VariableInspectionTree) -> TextTree:
    """Adapt static inspection to text without expanding committed snapshots.

    :param tree: Detached inspection structure with its original raw fields intact.
    :returns: Protected node text and alphabetically ordered visible descendants.
    """
    children = (
        ()
        if tree.masked or tree.status is VariableInspectionStatus.CACHED
        else tuple(
            build_inspection_display(child)
            for child in sorted(
                tree.dependencies, key=lambda child: sort_display_name(str(child.var_name))
            )
        )
    )
    return render_inspection(tree), children


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def canonical_value_repr(value: object) -> str:
    """Return one physical line for an arbitrary current value.

    :param value: Opaque cached value, host object, or exception.
    :returns: Canonical LCL source for supported AST values, otherwise repr.

    .. note::
       Unsupported custom AST nodes retain ordinary repr; all output is one line.
    """
    return render_canonical_value(value)


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
    return f"({type(value).__name__}) {compact_repr(value)}"


@guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
def compact_repr(value: object) -> str:
    """Render canonical values safely without truncating inspection output.

    :param value: Current cached or host value.
    :returns: Protected single-line canonical AST or ordinary representation.
    """
    return safe_repr(value, renderer=canonical_value_repr, max_length=None)
