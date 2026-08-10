"""Unit tests mirroring :mod:`pylcl.lang.evaluator.calls`."""

from collections.abc import AsyncIterator

import pytest

from pylcl import evaluate
from pylcl.ast import LclCall, LclConstant
from pylcl.errors import LclEvaluationError
from pylcl.lang.parser import parse_expression
from pylcl.source import SourceSpan
from pylcl.types import VarName


@pytest.mark.asyncio
async def test_all_argument_wrappers_build_one_call() -> None:
    """Positional, starred, keyword, and mapping arguments retain order."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def function(*args: object, **kwargs: object) -> str:
        calls.append((args, kwargs))
        return "called"

    values = {
        "function": function,
        "items": [2, 3],
        "options": {"other": 4},
    }
    source = "function(1, *items, key=2, **options)"
    assert await evaluate(parse_expression(source), values) == "called"
    assert calls == [((1, 2, 3), {"key": 2, "other": 4})]


@pytest.mark.asyncio
async def test_keyword_unpack_can_be_followed_by_an_explicit_keyword() -> None:
    """Argument assembly continues after a mapping expansion in source order."""

    def function(**values: object) -> dict[str, object]:
        return values

    result = await evaluate(
        parse_expression("function(**options, final=3)"),
        {"function": function, "options": {"first": 1, "second": 2}},
    )
    assert result == {"first": 1, "second": 2, "final": 3}


@pytest.mark.asyncio
async def test_star_argument_accepts_async_iterable() -> None:
    """Async-only argument expansion completes before invocation."""

    class AsyncItems:
        async def __aiter__(self) -> AsyncIterator[int]:
            yield 20
            yield 22

    def add(*values: int) -> int:
        return sum(values)

    values = {"add": add, "items": AsyncItems()}
    assert await evaluate(parse_expression("add(*items)"), values) == 42


@pytest.mark.asyncio
async def test_awaitable_call_result_is_resolved() -> None:
    """A callable's coroutine result is auto-awaited by central evaluation."""

    async def answer() -> int:
        return 42

    assert await evaluate(parse_expression("answer()"), {"answer": answer}) == 42


@pytest.mark.asyncio
async def test_callable_and_arguments_evaluate_left_to_right() -> None:
    """Resolver access proves callable-first and source-order argument handling."""
    names: list[VarName] = []

    def function(*values: object, **options: object) -> tuple[object, ...]:
        return (*values, *options.values())

    class RecordingResolver:
        async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
            names.append(name)
            return {"function": function, "first": 1, "second": 2}[str(name)]

    source = "function(first, named=second)"
    assert await evaluate(parse_expression(source), RecordingResolver()) == (1, 2)
    assert names == [VarName("function"), VarName("first"), VarName("second")]


@pytest.mark.asyncio
async def test_duplicate_and_non_string_keywords_are_rejected() -> None:
    """Keyword merging validates names before the target callable runs."""
    called = False

    def function(**values: object) -> None:
        nonlocal called
        called = True

    with pytest.raises(LclEvaluationError, match="duplicate keyword") as duplicate:
        await evaluate(
            parse_expression("function(key=1, **options)"),
            {"function": function, "options": {"key": 2}},
        )
    assert isinstance(duplicate.value.__cause__, TypeError)
    with pytest.raises(LclEvaluationError, match="string keys") as invalid_key:
        await evaluate(
            parse_expression("function(**options)"),
            {"function": function, "options": {1: 2}},
        )
    assert isinstance(invalid_key.value.__cause__, TypeError)
    with pytest.raises(LclEvaluationError, match="requires a mapping") as invalid_mapping:
        await evaluate(
            parse_expression("function(**options)"),
            {"function": function, "options": [1, 2]},
        )
    assert isinstance(invalid_mapping.value.__cause__, TypeError)
    assert called is False


@pytest.mark.asyncio
async def test_non_callable_value_retains_type_error() -> None:
    """A non-callable protocol failure is preserved as the public error cause."""
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression("value()"), {"value": 42})
    assert isinstance(caught.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_call_rejects_invalid_ast_argument_wrapper() -> None:
    """A manually malformed argument is rejected instead of silently skipped."""
    malformed = LclCall(
        LclConstant(value=lambda: None),
        (LclConstant(value="invalid"),),  # type: ignore[arg-type]
    )
    with pytest.raises(LclEvaluationError, match="unsupported call argument") as caught:
        await evaluate(malformed)
    assert isinstance(caught.value.__cause__, TypeError)
