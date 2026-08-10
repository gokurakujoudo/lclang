"""Frame-owned dependency graph, trace staging, and snapshot publication."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from lclang.errors import LclEvaluationError, LclNameError
from lclang.lang.evaluator.context import Resolver
from lclang.runtime.dependency.graph import DependencyGraph, build_dependency_graph
from lclang.runtime.dependency.reconciliation import reconcile_dependency_edges
from lclang.runtime.dependency.snapshot import DependencySnapshot
from lclang.runtime.dependency.tracing import DependencyTrace, TracingResolver
from lclang.runtime.frame.lifecycle import InternalFrameLifecycle
from lclang.runtime.modules import Module
from lclang.types import VarName


class InternalFrameDependencies:
    """Own static graph data and published traces for one Frame.

    .. note::
       Traces are staged separately and published only after evaluation commits.
    """

    def __init__(self, module: Module) -> None:
        """Analyze the immutable module and start without runtime traces.

        :param module: Definition snapshot owned by the Frame.
        """
        self.graph: DependencyGraph = build_dependency_graph(module)
        self.traces: dict[str, DependencyTrace] = {}

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

    def publish(self, name: str, trace: DependencyTrace) -> None:
        """Replace committed runtime evidence for one definition.

        :param name: Definition whose evaluation committed.
        :param trace: Complete trace collected by that evaluation.
        """
        self.traces[name] = trace

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

    def clear(self) -> None:
        """Discard all committed runtime observations."""
        self.traces.clear()


class InternalSnapshotFrame(Protocol):
    """Describe Frame state required for hierarchical snapshots.

    :param module: Immutable local definition snapshot.
    :param values: Read-only host binding view.
    :param parent: Optional lexical parent Frame.
    """

    module: Module
    values: Mapping[str, object]
    parent: InternalSnapshotFrame | None
    _lifecycle: InternalFrameLifecycle
    _dependencies: InternalFrameDependencies

    def dependency_snapshot(self, name: str) -> DependencySnapshot:
        """Return dependency evidence selected through hierarchy lookup.

        :param name: Requested definition name.
        :returns: Snapshot owned by the selected definition Frame.
        """
        ...


class InternalDependencySnapshotApi:
    """Provide the public hierarchical dependency-snapshot method."""

    def dependency_snapshot(self, name: str) -> DependencySnapshot:
        """Return point-in-time dependency evidence for one owned definition.

        :param name: Non-empty definition name to inspect.
        :returns: Immutable static, dynamic, and reconciled edge evidence.
        :raises ValueError: If *name* is empty.
        :raises LclEvaluationError: If *name* selects a host binding.
        :raises LclNameError: If *name* is absent from the Frame hierarchy.
        :raises LclClosedFrameError: If this Frame is closing or closed.

        .. note::
           Parent definitions are inspected in their owning parent Frame.
        """
        frame = cast(InternalSnapshotFrame, self)
        frame._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        if name in frame.module.definitions:
            return frame._dependencies.snapshot(name)
        if name in frame.values:
            message = f"host binding has no dependency snapshot: {name}"
            raise LclEvaluationError(message)
        if frame.parent is not None:
            return frame.parent.dependency_snapshot(name)
        raise LclNameError(f"unknown variable: {name}")
