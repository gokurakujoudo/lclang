"""Runtime free-name observation through a resolver decorator.

Defines ``DependencyTrace``, ``TracingResolver``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from lclang.common.identifiers import VarName
from lclang.common.scoped_proxy import ScopedProxyValue
from lclang.common.source_location import SourceSpan
from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.lang.engine.evaluator.name_resolver import Resolver
from lclang.lang.runtime.dependency.dependency_types import DependencyEdge, DependencyKind


@guard_constructor(LclValidationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
class DependencyTrace:
    """Collect bounded runtime dependency occurrences for one definition.

    :param source: Non-empty definition name that owns every observation.
    :raises LclValidationError: If *source* is empty.

    .. note::
       Exact repeated occurrences are idempotent and first-observation order is
       stable.
    """

    def __init__(self, source: VarName) -> None:
        """Create an initially empty per-definition trace.

        :param source: Non-empty definition owning every observation.
        :raises LclValidationError: If *source* is empty.
        """
        if not source:
            raise LclValidationError(
                "dependency trace source cannot be empty",
                code=RuntimeErrorCode.E41_DEPENDENCY_SNAPSHOT_SOURCE_CANNOT_BE_EMPTY,
            )
        self.source = source
        self._observations: dict[tuple[VarName, SourceSpan], DependencyEdge] = {}

    @property
    @guard_failure(LclEvaluationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
    def edges(self) -> tuple[DependencyEdge, ...]:
        """Return an immutable point-in-time observation snapshot.

        :returns: Dynamic edges in first-observation order.

        .. note::
           A previously returned tuple never changes after later recording.
        """
        return tuple(self._observations.values())

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
    def record(self, target: VarName, span: SourceSpan) -> None:
        """Record one actual free-name resolution occurrence.

        :param target: Non-empty requested free-variable name.
        :param span: Exact source range of the requesting name node.
        :returns: ``None`` after the occurrence is present in the trace.
        :raises LclValidationError: If *target* is empty.

        .. note::
           Repeating the same target and span does not grow the trace.
        """
        if not target:
            raise LclValidationError(
                "dependency trace target cannot be empty",
                code=RuntimeErrorCode.E41_DEPENDENCY_SNAPSHOT_SOURCE_CANNOT_BE_EMPTY,
            )
        key = (target, span)
        if key not in self._observations:
            self._observations[key] = DependencyEdge(
                self.source,
                target,
                DependencyKind.DYNAMIC,
                span,
            )


@guard_constructor(LclValidationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
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

    @guard_async_failure(LclEvaluationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
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
        if isinstance(result, ScopedProxyValue):

            def record_target(target: str, target_span: SourceSpan) -> None:
                """Record a scoped target using its nominal variable name.

                :param target: Qualified target name supplied by the proxy.
                :param target_span: Source location of the scoped lookup.
                """
                self.trace.record(VarName(target), target_span)

            return cast(Any, result).with_trace(record_target)
        self.trace.record(name, span)
        return result
