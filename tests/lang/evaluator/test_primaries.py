"""Unit tests mirroring :mod:`pylcl.lang.evaluator.primaries`."""

from dataclasses import dataclass

import pytest

from pylcl import evaluate
from pylcl.errors import LclEvaluationError
from pylcl.lang.parser import parse_expression
from pylcl.source import SourceSpan
from pylcl.types import VarName


@dataclass
class Leaf:
    """Provide a simple attribute-bearing test value."""

    value: int


@dataclass
class Root:
    """Provide a nested attribute-bearing test value."""

    child: Leaf


@pytest.mark.asyncio
async def test_attribute_chains_and_safe_none_access() -> None:
    """Ordinary chains resolve while a null-safe receiver returns None."""
    values = {"root": Root(Leaf(42)), "missing": None}
    assert await evaluate(parse_expression("root.child.value"), values) == 42
    assert await evaluate(parse_expression("missing?.child?.value"), values) is None


@pytest.mark.asyncio
async def test_safe_attribute_does_not_hide_non_null_failure() -> None:
    """Null safety structures rather than suppresses a descriptor failure."""
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("value?.missing"), {"value": object()})
    assert isinstance(caught.value.__cause__, AttributeError)


@pytest.mark.asyncio
async def test_subscript_slice_and_tuple_index_values() -> None:
    """Subscriptions receive evaluated scalar, slice, and tuple indices."""

    class IndexRecorder:
        def __getitem__(self, index: object) -> object:
            return index

    values = {"items": [0, 1, 2, 3, 4], "recorder": IndexRecorder()}
    assert await evaluate(parse_expression("items[1]"), values) == 1
    assert await evaluate(parse_expression("items[1:4:2]"), values) == [1, 3]
    assert await evaluate(parse_expression("recorder[1, 2]"), values) == (1, 2)


@pytest.mark.asyncio
async def test_receiver_precedes_index_evaluation() -> None:
    """A subscription resolves its receiver before resolving its index."""

    class RecordingResolver:
        def __init__(self) -> None:
            self.names: list[VarName] = []

        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            self.names.append(name)
            return {"receiver": [42], "index": 0}[str(name)]

    resolver = RecordingResolver()
    assert await evaluate(parse_expression("receiver[index]"), resolver) == 42
    assert resolver.names == [VarName("receiver"), VarName("index")]
