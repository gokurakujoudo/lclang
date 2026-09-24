# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Lazy Frame lookup, evaluation, and cache publication."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame

import asyncio
from typing import Any, cast

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
from lclang.runtime.frame.binding_lookup import (
    BindingSelection,
    find_scoped_factory,
    is_name_masked,
    select_binding,
)
from lclang.runtime.frame.evaluation_flights import (
    internal_check_cycle,
    internal_enter_flight,
    internal_leave_flight,
)
from lclang.runtime.frame.evaluation_limits import internal_budget_scope
from lclang.runtime.frame.fallback import NO_FALLBACK
from lclang.scope_proxy import FrameProxy
from lclang.source import SourceSpan
from lclang.types import VarName


async def get_value(requester: Frame, name: str, fallback: object = NO_FALLBACK) -> object:
    """Resolve one local definition or host binding.

    :param requester: Concrete Frame providing the operation state.
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
    frame = requester
    frame._lifecycle.ensure_open(None)
    if not name:
        raise ValueError("variable name cannot be empty")
    selected = select_binding(requester, name)
    if selected.owner is None:
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
    return await read_selected_binding(requester, name, None, selected)


async def evaluate_expression(requester: Frame, expr: str) -> object:
    """Evaluate one unnamed expression against this open Frame.

    :param requester: Concrete Frame providing the operation state.
    :param expr: Complete LCL source expression.
    :returns: Fully resolved uncached result.
    :raises TypeError: If *expr* is not a string.
    :raises LclClosedFrameError: If Frame closing has begun.

    .. note::
       Named dependencies retain ordinary Frame caching while the root
       expression uses ``<expr>`` as its lexical ``lhs()`` owner.
    """
    frame = requester
    frame._lifecycle.ensure_open(None)
    if not isinstance(expr, str):
        raise TypeError("Frame expression must be a string")
    node = parse_expression(expr)
    with definition_scope("<expr>"), internal_budget_scope(frame.limits):
        return await evaluate_lcl(node, cast(Resolver, requester))


async def resolve_name(requester: Frame, name: VarName, *, span: SourceSpan) -> object:
    """Resolve a name for the language evaluator.

    :param requester: Concrete Frame providing the operation state.
    :param name: Variable requested by a semantic name node.
    :param span: Requesting source range for missing-name diagnostics.
    :returns: Cached or newly evaluated value.
    :raises LclNameError: If no definition or host binding exists.
    :raises Exception: If definition evaluation fails.

    .. note::
       Local module definitions shadow host bindings with the same name.
    """
    frame = requester
    frame._lifecycle.ensure_open(span)
    return await requester.get_resolved(str(name), span)


async def get_resolved(requester: Frame, name: str, span: SourceSpan | None) -> object:
    """Resolve one validated name while retaining its diagnostic span.

    :param requester: Concrete Frame providing the operation state.
    :param name: Non-empty variable name.
    :param span: Optional requesting source range.
    :returns: Cached, host-provided, or newly evaluated value.
    :raises LclNameError: If hierarchy lookup cannot select the name.
    :raises Exception: If the selected definition evaluation fails.

    .. note::
       Waiters shield a shared owner Task from caller cancellation.
    """
    frame = requester
    frame._lifecycle.ensure_open(span)
    internal_check_cycle(requester, name, span)
    return await read_selected_binding(requester, name, span, select_binding(requester, name))


async def read_selected_binding(
    requester: Frame,
    name: str,
    span: SourceSpan | None,
    selected: BindingSelection,
) -> object:
    """Read a selected binding without repeating hierarchy classification.

    :param requester: Concrete Frame providing the operation state.
    :param name: Normalized selected name.
    :param span: Optional requesting source range.
    :param selected: Selection made by this operation before any await.
    :returns: Proxy, host value or committed definition result.
    :raises LclNameError: If selection has no owner.
    :raises Exception: If evaluation or lifecycle validation fails.
    """
    frame = requester
    frame._lifecycle.ensure_open(span)
    internal_check_cycle(requester, name, span)
    owner = selected.owner
    if owner is None:
        if internal_verbose_enabled():
            internal_trace(
                "lookup",
                f"name={name!r} owner={str(frame.frame_id)!r} source=missing",
            )
        raise LclNameError(f"unknown variable: {name}", span=span)
    binding_kind = selected.kind
    if binding_kind == "proxy":
        return FrameProxy(cast(object, requester), tuple(name.split(".")))  # type: ignore[arg-type]
    if binding_kind == "factory":
        factory = find_scoped_factory(owner, name)
        return cast(Any, factory).bind(requester, tuple(name.split(".")))
    frame = owner
    frame._lifecycle.ensure_open(span)
    internal_check_cycle(owner, name, span)
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
            task = asyncio.create_task(owner.evaluate_definition(name))
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


async def evaluate_definition(requester: Frame, name: str) -> object:
    """Evaluate and atomically publish one owned definition snapshot.

    :param requester: Concrete Frame providing the operation state.
    :param name: Definition name owned by this Frame.
    :returns: Newly evaluated value after cache and trace publication.
    :raises Exception: If evaluation fails after publishing its failure.

    .. note::
       Flight cleanup occurs even for cancellation or base exceptions.
    """
    frame = requester
    token = internal_enter_flight(requester, name)
    trace, resolver = frame._dependencies.stage(name, cast(Resolver, requester))
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
