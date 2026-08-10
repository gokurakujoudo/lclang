"""Unit tests mirroring :mod:`lclang.lang.evaluator.context`."""

import pytest

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
