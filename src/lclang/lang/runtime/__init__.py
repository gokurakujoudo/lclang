"""Public runtime module and Frame values.

Exports ``DependencyEdge``, ``DependencyGraph``, ``DependencyKind``,
``DependencyReference``, ``DependencyReconciliation``, ``DependencySnapshot``,
``DependencyTrace``, ``EvaluationLimits``, ``Frame``, ``FrameBindingKind``,
``FrameDependencyBinding``, ``FrameDependencyEdge``, ``FrameDependencyGraph``,
``FrameFactory``, ``FrameProxy``, ``FRAME_PROXY``, ``Module``, ``NO_FALLBACK``, ``Preset``,
``TracingResolver``, ``VariableInspectionStatus``, ``VariableInspectionTree``,
``analyze_dependencies``, ``build_dependency_graph``, ``reconcile_dependency_edges``,
``topological_order``.
"""

from lclang.lang.common.frame_proxy_marker import FRAME_PROXY
from lclang.lang.runtime.dependency.ast_dependency_analysis import analyze_dependencies
from lclang.lang.runtime.dependency.dependency_ordering import topological_order
from lclang.lang.runtime.dependency.dependency_reconciliation import (
    DependencyReconciliation,
    reconcile_dependency_edges,
)
from lclang.lang.runtime.dependency.dependency_snapshot import DependencySnapshot
from lclang.lang.runtime.dependency.dependency_trace import DependencyTrace, TracingResolver
from lclang.lang.runtime.dependency.dependency_types import (
    DependencyEdge,
    DependencyKind,
    DependencyReference,
)
from lclang.lang.runtime.dependency.frame.frame_dependency_graph import (
    FrameBindingKind,
    FrameDependencyBinding,
    FrameDependencyEdge,
    FrameDependencyGraph,
)
from lclang.lang.runtime.dependency.module_dependency_graph import (
    DependencyGraph,
    build_dependency_graph,
)
from lclang.lang.runtime.frame import (
    NO_FALLBACK,
    EvaluationLimits,
    Frame,
    FrameFactory,
    FrameProxy,
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.lang.runtime.module import Module
from lclang.lang.runtime.preset import Preset

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "DependencyEdge",
    "DependencyGraph",
    "DependencyKind",
    "DependencyReference",
    "DependencyReconciliation",
    "DependencySnapshot",
    "DependencyTrace",
    "EvaluationLimits",
    "Frame",
    "FrameBindingKind",
    "FrameDependencyBinding",
    "FrameDependencyEdge",
    "FrameDependencyGraph",
    "FrameFactory",
    "FrameProxy",
    "FRAME_PROXY",
    "Module",
    "NO_FALLBACK",
    "Preset",
    "TracingResolver",
    "VariableInspectionStatus",
    "VariableInspectionTree",
    "analyze_dependencies",
    "build_dependency_graph",
    "reconcile_dependency_edges",
    "topological_order",
]
