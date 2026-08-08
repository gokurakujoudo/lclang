"""Lazy Frame lookup, evaluation, and cache publication."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Protocol, cast

from pylcl.errors import LclNameError
from pylcl.lang.evaluator import evaluate
from pylcl.lang.evaluator.awaitables import resolve_awaitable
from pylcl.lang.evaluator.context import Resolver
from pylcl.lang.evaluator.definition_context import definition_scope
from pylcl.runtime.frame.dependencies import _FrameDependencies
from pylcl.runtime.frame.flights import _check_cycle, _enter_flight, _leave_flight
from pylcl.runtime.frame.lifecycle import _FrameLifecycle
from pylcl.runtime.frame.limits import EvaluationLimits, _budget_scope
from pylcl.runtime.frame.lookup import find_frame
from pylcl.runtime.modules import Module
from pylcl.source import SourceSpan
from pylcl.types import VarName


class EvaluationFrame(Protocol):
    """Describe concrete Frame state used during lazy evaluation.

    :param module: Immutable local definitions.
    :param values: Read-only host bindings.
    :param limits: Evaluation resource ceilings.

    .. note::
       Mutable cache and flight dictionaries remain privately Frame-owned.
    """

    module: Module
    values: Mapping[str, object]
    limits: EvaluationLimits
    _results: dict[str, object]
    _failures: dict[str, Exception]
    _inflight: dict[str, asyncio.Task[object]]
    _dependencies: _FrameDependencies
    _lifecycle: _FrameLifecycle


class FrameEvaluationApi:
    """Provide lazy name evaluation for a concrete Frame.

    .. note::
       Owner delegation keeps parent definitions in their lexical Frame.
    """

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
        frame = cast(EvaluationFrame, self)
        frame._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        return await self.get_resolved(name, None)

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
        frame = cast(EvaluationFrame, self)
        frame._lifecycle.ensure_open(span)
        return await self.get_resolved(str(name), span)

    async def get_resolved(self, name: str, span: SourceSpan | None) -> object:
        """Resolve one validated name while retaining its diagnostic span.

        :param name: Non-empty variable name.
        :param span: Optional requesting source range.
        :returns: Cached, host-provided, or newly evaluated value.
        :raises LclNameError: If hierarchy lookup cannot select the name.
        :raises Exception: If the selected definition evaluation fails.

        .. note::
           Waiters shield a shared owner Task from caller cancellation.
        """
        frame = cast(EvaluationFrame, self)
        frame._lifecycle.ensure_open(span)
        _check_cycle(self, name, span)
        owner = find_frame(self, name)
        if owner is None:
            raise LclNameError(f"unknown variable: {name}", span=span)
        if owner is not self:
            return await cast(FrameEvaluationApi, owner).get_resolved(name, span)
        if name in frame._results:
            return frame._results[name]
        if name in frame._failures:
            raise frame._failures[name]
        if name in frame.module.definitions:
            task = frame._inflight.get(name)
            if task is None:
                task = asyncio.create_task(self.evaluate_definition(name))
                frame._inflight[name] = task
            return await asyncio.shield(task)
        return await resolve_awaitable(frame.values[name])

    async def evaluate_definition(self, name: str) -> object:
        """Evaluate and atomically publish one owned definition snapshot.

        :param name: Definition name owned by this Frame.
        :returns: Newly evaluated value after cache and trace publication.
        :raises Exception: If evaluation fails after publishing its failure.

        .. note::
           Flight cleanup occurs even for cancellation or base exceptions.
        """
        frame = cast(EvaluationFrame, self)
        token = _enter_flight(self, name)
        trace, resolver = frame._dependencies.stage(name, cast(Resolver, self))
        try:
            try:
                with definition_scope(name), _budget_scope(frame.limits):
                    result = await evaluate(frame.module.definitions[name], resolver)
            except Exception as error:
                frame._lifecycle.commit_failure(name, error)
                frame._dependencies.publish(name, trace)
                raise
            frame._lifecycle.commit_result(name, result)
            frame._dependencies.publish(name, trace)
            return result
        finally:
            _leave_flight(token)
            frame._inflight.pop(name, None)
