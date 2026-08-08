"""Unit tests mirroring :mod:`pylcl.runtime.dependency.tracing`."""

from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from pylcl import evaluate
from pylcl.errors import LclNameError
from pylcl.lang.evaluator.context import MappingResolver
from pylcl.lang.parser import parse_expression
from pylcl.runtime import DependencyKind, DependencyTrace, TracingResolver
from pylcl.types import VarName


def test_trace_validates_source_and_retains_bounded_ordered_snapshots() -> None:
    """Exact repeat observations deduplicate without mutating old snapshots."""
    first_span = parse_expression("target").span
    later_span = parse_expression(" target").span
    with pytest.raises(ValueError):
        DependencyTrace(VarName(""))
    trace = DependencyTrace(VarName("source"))
    with pytest.raises(ValueError):
        trace.record(VarName(""), first_span)
    trace.record(VarName("target"), first_span)
    snapshot = trace.edges
    trace.record(VarName("target"), first_span)
    trace.record(VarName("target"), later_span)
    assert len(snapshot) == 1
    assert tuple(edge.span for edge in trace.edges) == (first_span, later_span)
    assert all(edge.kind is DependencyKind.DYNAMIC for edge in trace.edges)


@pytest.mark.asyncio
async def test_tracing_resolver_records_before_success_and_missing_failure() -> None:
    """Parent results and missing-name errors pass through after observation."""
    trace = DependencyTrace(VarName("source"))
    resolver = TracingResolver(trace, MappingResolver({"present": 7}))
    present = parse_expression("present")
    missing = parse_expression("missing")
    assert await resolver.resolve(VarName("present"), span=present.span) == 7
    with pytest.raises(LclNameError):
        await resolver.resolve(VarName("missing"), span=missing.span)
    assert tuple(edge.target for edge in trace.edges) == (
        VarName("present"),
        VarName("missing"),
    )


@pytest.mark.asyncio
async def test_captured_resolver_traces_later_free_names_not_local_parameters() -> None:
    """A closure extends its defining trace only for delegated free lookups."""
    trace = DependencyTrace(VarName("function"))
    resolver = TracingResolver(trace, MappingResolver({"outer": 40}))
    function = await evaluate(parse_expression("def (x): x + outer"), resolver)
    before_call = trace.edges
    assert before_call == ()
    call = cast(Callable[..., Awaitable[object]], function)
    assert await call(2) == 42
    assert len(trace.edges) == 1
    assert trace.edges[0].target == VarName("outer")


def test_distinct_traces_share_no_observations() -> None:
    """Per-definition trace values own independent mutable observation sets."""
    span = parse_expression("value").span
    first = DependencyTrace(VarName("first"))
    second = DependencyTrace(VarName("second"))
    first.record(VarName("value"), span)
    assert len(first.edges) == 1
    assert second.edges == ()
