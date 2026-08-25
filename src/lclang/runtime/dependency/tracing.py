"""Runtime free-name observation through a resolver decorator."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.lang.evaluator.context import Resolver
from lclang.runtime.dependency.model import DependencyEdge, DependencyKind
from lclang.scope_proxy import FrameProxy
from lclang.source import SourceSpan
from lclang.types import VarName


class DependencyTrace:
    """Collect bounded runtime dependency occurrences for one definition.

    :param source: Non-empty definition name that owns every observation.
    :raises ValueError: If *source* is empty.

    .. note::
       Exact repeated occurrences are idempotent and first-observation order is
       stable.
    """

    def __init__(self, source: VarName) -> None:
        """Create an initially empty per-definition trace.

        :param source: Non-empty definition owning every observation.
        :raises ValueError: If *source* is empty.
        """
        if not source:
            raise ValueError("dependency trace source cannot be empty")
        self.source = source
        self._observations: dict[tuple[VarName, SourceSpan], DependencyEdge] = {}

    @property
    def edges(self) -> tuple[DependencyEdge, ...]:
        """Return an immutable point-in-time observation snapshot.

        :returns: Dynamic edges in first-observation order.

        .. note::
           A previously returned tuple never changes after later recording.
        """
        return tuple(self._observations.values())

    def record(self, target: VarName, span: SourceSpan) -> None:
        """Record one actual free-name resolution occurrence.

        :param target: Non-empty requested free-variable name.
        :param span: Exact source range of the requesting name node.
        :returns: ``None`` after the occurrence is present in the trace.
        :raises ValueError: If *target* is empty.

        .. note::
           Repeating the same target and span does not grow the trace.
        """
        if not target:
            raise ValueError("dependency trace target cannot be empty")
        key = (target, span)
        if key not in self._observations:
            self._observations[key] = DependencyEdge(
                self.source,
                target,
                DependencyKind.DYNAMIC,
                span,
            )


@dataclass(frozen=True, slots=True)
class TracingResolver:
    """Record free-name requests before delegating to another resolver.

    :param trace: Per-definition observation sink retained by reference.
    :param parent: Resolver providing the actual lookup semantics.

    .. note::
       Closures retaining this resolver continue extending the same trace.
    """

    trace: DependencyTrace
    parent: Resolver

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Record and delegate one free-name lookup.

        :param name: Variable requested by a semantic name node.
        :param span: Exact requesting source range.
        :returns: Parent resolver's immediate or deferred result.
        :raises Exception: If the parent resolver rejects or fails the lookup.

        .. note::
           Recording precedes delegation, so failed lookups remain observable.
        """
        try:
            result = await self.parent.resolve(name, span=span)
        except BaseException:
            self.trace.record(name, span)
            raise
        if isinstance(result, FrameProxy):
            return result.with_trace(
                lambda target, target_span: self.trace.record(
                    VarName(target),
                    target_span,
                )
            )
        self.trace.record(name, span)
        return result
