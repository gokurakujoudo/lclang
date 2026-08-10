"""Unit tests mirroring :mod:`lclang.lang.evaluator.dispatch`."""

from collections.abc import Coroutine

import pytest

import lclang
from lclang.ast import LclStringText
from lclang.errors import LclEvaluationError, LclNameError
from lclang.lang.parser import parse_expression
from lclang.source import SourceOrigin, SourceSpan
from lclang.types import SourceName, VarName


@pytest.mark.asyncio
async def test_evaluate_constants_and_mapping_names() -> None:
    """Core leaf nodes produce literals and source mapping values."""
    values: dict[str, object] = {"answer": 42}
    assert await lclang.evaluate(parse_expression("None"), values) is None
    assert await lclang.evaluate(parse_expression("answer"), values) == 42
    assert values == {"answer": 42}


@pytest.mark.asyncio
async def test_name_values_are_automatically_awaited() -> None:
    """A deferred mapping value is resolved before evaluation returns."""

    async def deferred() -> int:
        return 42

    awaitable: Coroutine[object, object, int] = deferred()
    assert await lclang.evaluate(parse_expression("answer"), {"answer": awaitable}) == 42


@pytest.mark.asyncio
async def test_custom_resolver_receives_name_and_ast_span() -> None:
    """Runtime resolvers receive enough source data for their own diagnostics."""

    class RecordingResolver:
        def __init__(self) -> None:
            self.call: tuple[VarName, SourceSpan] | None = None

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.call = (name, span)
            return "value"

    origin = SourceOrigin(SourceName("named.lcl"))
    node = parse_expression("item", origin=origin)
    resolver = RecordingResolver()
    assert await lclang.evaluate(node, resolver) == "value"
    assert resolver.call == (VarName("item"), node.span)


@pytest.mark.asyncio
async def test_missing_name_and_unsupported_node_are_structured() -> None:
    """Expected lookup and dispatch failures retain the responsible span."""
    missing = parse_expression("missing")
    with pytest.raises(LclNameError) as name_error:
        await lclang.evaluate(missing)
    assert name_error.value.span == missing.span

    unsupported_node = LclStringText(text="orphan", span=missing.span)
    with pytest.raises(LclEvaluationError, match="unsupported AST node") as unsupported:
        await lclang.evaluate(unsupported_node)
    assert unsupported.value.span == unsupported_node.span


@pytest.mark.asyncio
async def test_custom_resolver_failures_become_structured_causes() -> None:
    """Resolver failures gain source context while retaining their exact cause."""
    failure = RuntimeError("resolver failed")

    class FailingResolver:
        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            raise failure

    with pytest.raises(LclEvaluationError) as caught:
        await lclang.evaluate(parse_expression("value"), FailingResolver())
    assert caught.value.__cause__ is failure


def test_root_exports_evaluator_services() -> None:
    """The async and sole sync boundaries are discoverable at package root."""
    assert "evaluate" in lclang.__all__
