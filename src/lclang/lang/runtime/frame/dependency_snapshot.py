# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Frame-owned dependency graph, trace staging, and snapshot publication.

Defines ``InternalFrameDependencies``, ``dependency_snapshot``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

if TYPE_CHECKING:
    from lclang.lang.runtime.frame.frame import Frame


from lclang.common.identifiers import VarName
from lclang.error import LclNameError
from lclang.lang.engine.evaluator.name_resolver import Resolver
from lclang.lang.runtime.dependency.dependency_reconciliation import reconcile_dependency_edges
from lclang.lang.runtime.dependency.dependency_snapshot import DependencySnapshot
from lclang.lang.runtime.dependency.dependency_trace import DependencyTrace, TracingResolver
from lclang.lang.runtime.dependency.module_dependency_graph import (
    DependencyGraph,
    build_dependency_graph,
)
from lclang.lang.runtime.frame.binding_lookup import select_binding
from lclang.lang.runtime.module import Module


@guard_constructor(LclValidationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
class InternalFrameDependencies:
    """Own static graph data and published traces for one Frame.

    .. note::
       Traces are staged separately and published only after evaluation commits.
    """

    def __init__(self, module: Module, scoped_names: tuple[str, ...] = ()) -> None:
        """Analyze the immutable module and start without runtime traces.

        :param module: Definition snapshot owned by the Frame.
        :param scoped_names: Effective qualified names visible from the Frame.
        """
        self.graph: DependencyGraph = build_dependency_graph(
            module,
            scoped_names=scoped_names,
        )
        self.traces: dict[str, DependencyTrace] = {}

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
    def stage(
        self,
        name: str,
        parent: Resolver,
    ) -> tuple[DependencyTrace, TracingResolver]:
        """Create an unpublished trace and resolver decorator.

        :param name: Definition about to be evaluated.
        :param parent: Resolver that performs actual lookup.
        :returns: Trace and matching resolver wrapper.
        """
        trace = DependencyTrace(VarName(name))
        return trace, TracingResolver(trace, parent)

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
    def publish(self, name: str, trace: DependencyTrace) -> None:
        """Replace committed runtime evidence for one definition.

        :param name: Definition whose evaluation committed.
        :param trace: Complete trace collected by that evaluation.
        """
        self.traces[name] = trace

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
    def snapshot(self, name: str) -> DependencySnapshot:
        """Combine static and committed runtime evidence.

        :param name: Owned module definition to inspect.
        :returns: Immutable reconciled dependency snapshot.
        :raises LclNameError: If *name* is not a module definition.
        """
        static_edges = self.graph.dependencies(name)
        trace = self.traces.get(name)
        dynamic_edges = () if trace is None else trace.edges
        reconciliation = reconcile_dependency_edges(static_edges, dynamic_edges)
        return DependencySnapshot(
            VarName(name),
            static_edges,
            dynamic_edges,
            reconciliation,
        )

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
    def clear(self) -> None:
        """Discard all committed runtime observations."""
        self.traces.clear()


@guard_failure(LclEvaluationError, RuntimeErrorCode.E34_DEPENDENCY_SNAPSHOT_NATIVE_FAILURE)
def dependency_snapshot(frame: Frame, name: str) -> DependencySnapshot:
    """Return point-in-time dependency evidence for one owned definition.

    :param frame: Concrete Frame providing the operation state.
    :param name: Non-empty definition name to inspect.
    :returns: Immutable static, dynamic, and reconciled edge evidence.
    :raises LclValidationError: If *name* is empty.
    :raises LclEvaluationError: If *name* selects a host binding.
    :raises LclNameError: If *name* is absent from the Frame hierarchy.
    :raises LclClosedFrameError: If this Frame is closing or closed.

    .. note::
       Parent definitions are inspected in their owning parent Frame.
    """
    frame._lifecycle.ensure_open(None)
    if not name:
        raise LclValidationError(
            "variable name cannot be empty", code=RuntimeErrorCode.E34_VARIABLE_NAME_CANNOT_BE_EMPTY
        )
    selected = select_binding(frame, name)
    owner = selected.owner
    if owner is None:
        raise LclNameError(f"unknown variable: {name}", code=RuntimeErrorCode.E34_UNKNOWN_VARIABLE)
    owner._lifecycle.ensure_open(None)
    if selected.kind == "proxy":
        raise LclEvaluationError(
            f"Frame proxy has no dependency snapshot: {name}",
            code=RuntimeErrorCode.E34_FRAME_PROXY_HAS_NO_DEPENDENCY_SNAPSHOT,
        )
    if selected.kind != "host" and name in owner.module.definitions:
        return owner._dependencies.snapshot(name)
    raise LclEvaluationError(
        f"host binding has no dependency snapshot: {name}",
        code=RuntimeErrorCode.E34_HOST_BINDING_HAS_NO_DEPENDENCY_SNAPSHOT,
    )
