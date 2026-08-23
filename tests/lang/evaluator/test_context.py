"""Unit tests mirroring :mod:`lclang.lang.evaluator.context`."""

import io
import logging

import pytest

from lclang.diagnostics import internal_trace, internal_verbose_scope
from lclang.errors import LclNameError
from lclang.lang.evaluator import MappingResolver, Resolver, ScopedResolver
from lclang.source import UNKNOWN_SPAN
from lclang.types import VarName


@pytest.mark.asyncio
async def test_mapping_resolver_reads_without_copying() -> None:
    """The mapping adapter observes current caller-owned values."""
    values: dict[str, object] = {"answer": 41}
    resolver = MappingResolver(values)
    values["answer"] = 42
    assert await resolver.resolve(VarName("answer"), span=UNKNOWN_SPAN) == 42
    assert isinstance(resolver, Resolver)


@pytest.mark.asyncio
async def test_mapping_resolver_reports_source_aware_missing_name() -> None:
    """A missing mapping key becomes the public name-error type."""
    resolver = MappingResolver({})
    with pytest.raises(LclNameError) as caught:
        await resolver.resolve(VarName("missing"), span=UNKNOWN_SPAN)
    assert caught.value.span is UNKNOWN_SPAN
    assert caught.value.code == "LCL2001"
    assert "missing" in caught.value.message


@pytest.mark.asyncio
async def test_scoped_resolver_overlays_without_mutating_parent() -> None:
    """Local bindings shadow parent names while unrelated lookup delegates."""
    parent_values = {"item": "parent", "other": 42}
    parent = MappingResolver(parent_values)
    scoped = ScopedResolver({"item": "local"}, parent)
    assert await scoped.resolve(VarName("item"), span=UNKNOWN_SPAN) == "local"
    assert await scoped.resolve(VarName("other"), span=UNKNOWN_SPAN) == 42
    assert parent_values == {"item": "parent", "other": 42}


@pytest.mark.asyncio
async def test_resolvers_trace_active_values_missing_names_and_await_failures() -> None:
    """Task-local tracing reports mapping and local resolver outcomes."""
    output = io.StringIO()
    logger = logging.Logger("resolver-trace", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(output))
    internal_trace("lookup", "silent")

    async def fail() -> object:
        """Raise one resolver-owned awaitable failure.

        :returns: No result because resolution fails.
        :raises RuntimeError: Always.
        """
        raise RuntimeError("resolver failed")

    mapping = MappingResolver({"answer": 42, "bad": fail()})
    scoped = ScopedResolver({"local": "value", "bad_local": fail()}, mapping)
    with internal_verbose_scope(logger):
        assert await mapping.resolve(VarName("answer"), span=UNKNOWN_SPAN) == 42
        with pytest.raises(LclNameError):
            await mapping.resolve(VarName("missing"), span=UNKNOWN_SPAN)
        with pytest.raises(RuntimeError):
            await mapping.resolve(VarName("bad"), span=UNKNOWN_SPAN)
        assert await scoped.resolve(VarName("local"), span=UNKNOWN_SPAN) == "value"
        with pytest.raises(RuntimeError):
            await scoped.resolve(VarName("bad_local"), span=UNKNOWN_SPAN)
    trace = output.getvalue()
    assert "source=external-provided value=(int) 42" in trace
    assert "source=missing" in trace
    assert "source=external-provided error=(RuntimeError)" in trace
    assert "source=local-provided value=(str) 'value'" in trace
    assert "source=local-provided error=(RuntimeError)" in trace
