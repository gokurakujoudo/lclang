"""Lazy Frame lookup, evaluation, and cache publication."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Protocol, cast

from lclang.diagnostics import (
    internal_masked_scope,
    internal_render_value,
    internal_trace,
    internal_verbose_enabled,
)
from lclang.errors import LclNameError
from lclang.lang.evaluator import evaluate as evaluate_lcl
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.lang.evaluator.context import Resolver
from lclang.lang.evaluator.definition_context import definition_scope
from lclang.lang.parser import parse_expression
from lclang.runtime.frame.dependencies import InternalFrameDependencies
from lclang.runtime.frame.fallback import NO_FALLBACK
from lclang.runtime.frame.flights import (
    internal_check_cycle,
    internal_enter_flight,
    internal_leave_flight,
)
from lclang.runtime.frame.lifecycle import InternalFrameLifecycle
from lclang.runtime.frame.limits import EvaluationLimits, internal_budget_scope
from lclang.runtime.frame.lookup import find_frame
from lclang.runtime.frame.scoped import (
    find_scoped_binding,
    find_scoped_factory,
    is_name_masked,
)
from lclang.runtime.modules import Module
from lclang.scope_proxy import FrameProxy
from lclang.source import SourceSpan
from lclang.types import FrameId, VarName


class EvaluationFrame(Protocol):
    """Describe concrete Frame state used during lazy evaluation.

    :param module: Immutable local definitions.
    :param frame_id: Diagnostic identifier for the owning Frame.
    :param values: Read-only host bindings.
    :param limits: Evaluation resource ceilings.
    :param native_values: Whether host bindings are canonical lclang values.

    .. note::
       Mutable cache and flight dictionaries remain privately Frame-owned.
    """

    module: Module
    frame_id: FrameId
    values: Mapping[str, object]
    limits: EvaluationLimits
    native_values: bool
    _results: dict[str, object]
    _failures: dict[str, Exception]
    _inflight: dict[str, asyncio.Task[object]]
    _dependencies: InternalFrameDependencies
    _lifecycle: InternalFrameLifecycle


class FrameEvaluationApi:
    """Provide lazy name evaluation for a concrete Frame.

    .. note::
       Owner delegation keeps parent definitions in their lexical Frame.
    """

    async def get(self, name: str, fallback: object = NO_FALLBACK) -> object:
        """Resolve one local definition or host binding.

        :param name: Non-empty variable name to resolve.
        :param fallback: Value returned unchanged when *name* is absent.
        :returns: Cached or newly evaluated value, or the explicit fallback.
        :raises ValueError: If *name* is empty.
        :raises LclNameError: If no binding exists and fallback is ``NO_FALLBACK``.
        :raises Exception: If definition evaluation fails.

        .. note::
           Successful values and ordinary failure instances are cached by name.
           A fallback is neither resolved nor cached and never replaces a
           failure from an existing definition.
        """
        frame = cast(EvaluationFrame, self)
        frame._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        if find_frame(self, name) is None:
            if fallback is NO_FALLBACK:
                if internal_verbose_enabled():
                    internal_trace(
                        "lookup",
                        f"name={name!r} owner={str(frame.frame_id)!r} source=missing",
                    )
                raise LclNameError(f"unknown variable: {name}")
            if internal_verbose_enabled():
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source=fallback "
                    f"value={internal_render_value(fallback)}",
                )
            return fallback
        return await self.get_resolved(name, None)

    async def evaluate(self, expr: str) -> object:
        """Evaluate one unnamed expression against this open Frame.

        :param expr: Complete LCL source expression.
        :returns: Fully resolved uncached result.
        :raises TypeError: If *expr* is not a string.
        :raises LclClosedFrameError: If Frame closing has begun.

        .. note::
           Named dependencies retain ordinary Frame caching while the root
           expression uses ``<expr>`` as its lexical ``lhs()`` owner.
        """
        frame = cast(EvaluationFrame, self)
        frame._lifecycle.ensure_open(None)
        if not isinstance(expr, str):
            raise TypeError("Frame expression must be a string")
        node = parse_expression(expr)
        with definition_scope("<expr>"), internal_budget_scope(frame.limits):
            return await evaluate_lcl(node, cast(Resolver, self))

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
        internal_check_cycle(self, name, span)
        owner = find_frame(self, name)
        if owner is None:
            if internal_verbose_enabled():
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source=missing",
                )
            raise LclNameError(f"unknown variable: {name}", span=span)
        scoped_owner, binding_kind = find_scoped_binding(self, name)
        if binding_kind == "proxy":
            return FrameProxy(cast(object, self), tuple(name.split(".")))  # type: ignore[arg-type]
        if binding_kind == "factory" and scoped_owner is not None:
            factory = find_scoped_factory(scoped_owner, name)
            return cast(Any, factory).bind(self, tuple(name.split(".")))
        if owner is not self:
            return await cast(FrameEvaluationApi, owner).get_resolved(name, span)
        if name in frame._results:
            result = frame._results[name]
            if internal_verbose_enabled():
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source=cached "
                    f"value={internal_render_value(result, masked=is_name_masked(frame, name))}",
                )
            return result
        if name in frame._failures:
            if internal_verbose_enabled():
                rendered_error = internal_render_value(
                    frame._failures[name],
                    masked=is_name_masked(frame, name),
                )
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source=cached-failure "
                    f"error={rendered_error}",
                )
            raise frame._failures[name]
        if name in frame.module.definitions:
            task = frame._inflight.get(name)
            source = "shared-lcl-evaluation" if task is not None else "lcl-evaluated"
            if task is None:
                task = asyncio.create_task(self.evaluate_definition(name))
                frame._inflight[name] = task
            try:
                result = await asyncio.shield(task)
            except BaseException as error:
                if internal_verbose_enabled():
                    internal_trace(
                        "lookup",
                        f"name={name!r} owner={str(frame.frame_id)!r} source={source} "
                        f"error={internal_render_value(error, masked=is_name_masked(frame, name))}",
                    )
                raise
            if internal_verbose_enabled():
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source={source} "
                    f"value={internal_render_value(result, masked=is_name_masked(frame, name))}",
                )
            return result
        source = "native-provided" if frame.native_values else "external-provided"
        try:
            result = await resolve_awaitable(frame.values[name])
        except BaseException as error:
            if internal_verbose_enabled():
                internal_trace(
                    "lookup",
                    f"name={name!r} owner={str(frame.frame_id)!r} source={source} "
                    f"error={internal_render_value(error, masked=is_name_masked(frame, name))}",
                )
            raise
        if internal_verbose_enabled():
            internal_trace(
                "lookup",
                f"name={name!r} owner={str(frame.frame_id)!r} source={source} "
                f"value={internal_render_value(result, masked=is_name_masked(frame, name))}",
            )
        return result

    async def evaluate_definition(self, name: str) -> object:
        """Evaluate and atomically publish one owned definition snapshot.

        :param name: Definition name owned by this Frame.
        :returns: Newly evaluated value after cache and trace publication.
        :raises Exception: If evaluation fails after publishing its failure.

        .. note::
           Flight cleanup occurs even for cancellation or base exceptions.
        """
        frame = cast(EvaluationFrame, self)
        token = internal_enter_flight(self, name)
        trace, resolver = frame._dependencies.stage(name, cast(Resolver, self))
        try:
            try:
                with (
                    definition_scope(name),
                    internal_budget_scope(frame.limits),
                    internal_masked_scope(is_name_masked(frame, name)),
                ):
                    result = await evaluate_lcl(frame.module.definitions[name], resolver)
            except Exception as error:
                frame._lifecycle.commit_failure(name, error)
                frame._dependencies.publish(name, trace)
                raise
            frame._lifecycle.commit_result(name, result)
            frame._dependencies.publish(name, trace)
            return result
        finally:
            internal_leave_flight(token)
            frame._inflight.pop(name, None)
