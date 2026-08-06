"""Lazy local runtime Frame evaluation and snapshot caching."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import MappingProxyType

from pylcl.errors import LclEvaluationError, LclNameError
from pylcl.lang.evaluator import evaluate
from pylcl.lang.evaluator.awaitables import resolve_awaitable
from pylcl.runtime.flight import _check_cycle, _enter_flight, _leave_flight
from pylcl.runtime.frame_dependencies import (
    _DependencySnapshotApi,
    _FrameDependencies,
)
from pylcl.runtime.lifecycle import _FrameLifecycle
from pylcl.runtime.limits import EvaluationLimits, _budget_scope
from pylcl.runtime.modules import Module
from pylcl.runtime.recalculation import _refresh_definition
from pylcl.source import SourceSpan
from pylcl.types import FrameId, VarName


class Frame(_DependencySnapshotApi):
    """Cache lazy evaluations for one runtime module instance.

    :param module: Immutable local definition snapshot.
    :param frame_id: Non-empty identifier for this runtime instance.
    :param values: Optional host bindings copied at construction time.
    :param parent: Optional ancestor used after local definitions and bindings.
    :param limits: Optional resource ceilings, or stable defaults when omitted.
    :raises ValueError: If *frame_id* or any host binding name is empty.

    .. note::
       Parent-owned definitions always evaluate and cache in their parent Frame.
    """

    def __init__(
        self,
        module: Module,
        frame_id: FrameId,
        *,
        values: Mapping[str, object] | None = None,
        parent: Frame | None = None,
        limits: EvaluationLimits | None = None,
    ) -> None:
        """Create an empty result cache over immutable inputs."""
        if not frame_id:
            raise ValueError("frame identifier cannot be empty")
        snapshot = {} if values is None else dict(values)
        if any(not name for name in snapshot):
            raise ValueError("host binding name cannot be empty")
        self.module = module
        self.frame_id = frame_id
        self.values: Mapping[str, object] = MappingProxyType(snapshot)
        self.parent = parent
        self.limits = EvaluationLimits() if limits is None else limits
        self._results: dict[str, object] = {}
        self._failures: dict[str, Exception] = {}
        self._inflight: dict[str, asyncio.Task[object]] = {}
        self._refreshes: dict[str, asyncio.Task[object]] = {}
        self._dependencies = _FrameDependencies(module)
        self._lifecycle = _FrameLifecycle(
            self._results,
            self._failures,
            self._inflight,
            self._refreshes,
            self._dependencies.clear,
        )

    @property
    def closed(self) -> bool:
        """Return whether owned cleanup has completely settled.

        :returns: ``True`` only after the shared close Task finishes.

        .. note::
           Requests are rejected while closing even though this remains false.
        """
        return self._lifecycle.closed

    async def close(self) -> None:
        """Cancel owned work and release cached resources exactly once.

        :returns: ``None`` after the shared close outcome settles.
        :raises LclEvaluationError: If an owned resource cleanup fails.
        :raises BaseException: If cleanup itself raises a direct base exception.

        .. note::
           Cancelling one caller does not cancel the owned close Task.
        """
        await self._lifecycle.close()

    async def get(self, name: str) -> object:
        """Resolve one local definition or host binding.

        :param name: Non-empty variable name to resolve.
        :returns: Cached or newly evaluated value.
        :raises ValueError: If *name* is empty.
        :raises LclNameError: If no definition or host binding exists.
        :raises Exception: If definition evaluation fails.

        .. note::
           Successful values and ordinary failure instances are cached by name.
        """
        self._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        return await self._get(name, None)

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Resolve a name for the language evaluator.

        :param name: Variable requested by a semantic name node.
        :param span: Requesting source range for missing-name diagnostics.
        :returns: Cached or newly evaluated value.
        :raises LclNameError: If no definition or host binding exists.
        :raises Exception: If definition evaluation fails.

        .. note::
           Local module definitions shadow host bindings with the same name.
        """
        self._lifecycle.ensure_open(span)
        return await self._get(str(name), span)

    async def recalculate(self, name: str) -> object:
        """Explicitly refresh one owned definition snapshot.

        :param name: Non-empty definition name to refresh.
        :returns: Newly evaluated result after its atomic cache commit.
        :raises ValueError: If *name* is empty.
        :raises LclEvaluationError: If *name* selects a host binding or fails.
        :raises LclNameError: If *name* is absent from the Frame hierarchy.

        .. note::
           Cached dependants and the previous snapshot are never invalidated.
        """
        self._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        if name in self.module.definitions:
            return await _refresh_definition(
                name,
                self._inflight,
                self._refreshes,
                self._evaluate_definition,
                lambda: self._lifecycle.ensure_open(None),
            )
        if name in self.values:
            message = f"host binding cannot be recalculated: {name}"
            raise LclEvaluationError(message)
        if self.parent is not None:
            return await self.parent.recalculate(name)
        raise LclNameError(f"unknown variable: {name}")

    async def _get(self, name: str, span: SourceSpan | None) -> object:
        self._lifecycle.ensure_open(span)
        _check_cycle(self, name, span)
        if name in self._results:
            return self._results[name]
        if name in self._failures:
            raise self._failures[name]
        if name in self.module.definitions:
            task = self._inflight.get(name)
            if task is None:
                task = asyncio.create_task(self._evaluate_definition(name))
                self._inflight[name] = task
            return await asyncio.shield(task)
        if name in self.values:
            return await resolve_awaitable(self.values[name])
        if self.parent is not None:
            return await self.parent._get(name, span)
        raise LclNameError(f"unknown variable: {name}", span=span)

    async def _evaluate_definition(self, name: str) -> object:
        token = _enter_flight(self, name)
        trace, resolver = self._dependencies.stage(name, self)
        try:
            try:
                with _budget_scope(self.limits):
                    result = await evaluate(self.module.definitions[name], resolver)
            except Exception as error:
                self._lifecycle.commit_failure(name, error)
                self._dependencies.publish(name, trace)
                raise
            self._lifecycle.commit_result(name, result)
            self._dependencies.publish(name, trace)
            return result
        finally:
            _leave_flight(token)
            self._inflight.pop(name, None)
