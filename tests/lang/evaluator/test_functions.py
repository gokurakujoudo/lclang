"""Unit tests mirroring :mod:`lclang.lang.evaluator.functions`."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from lclang import evaluate
from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression


@pytest.mark.asyncio
async def test_function_defaults_and_body_evaluate() -> None:
    """A function value binds a supplied argument and its created default."""
    function = await evaluate(parse_expression("(x, y=1) -> x + y"))
    call = cast(Callable[..., Awaitable[object]], function)
    assert await call(2) == 3
    assert await call(2, 3) == 5


@pytest.mark.asyncio
async def test_defaults_evaluate_once_when_function_is_created() -> None:
    """Later resolver updates do not recompute an already bound default."""
    values: dict[str, object] = {"base": 1}
    function = await evaluate(parse_expression("(x=base) -> x"), values)
    values["base"] = 2
    call = cast(Callable[..., Awaitable[object]], function)
    assert await call() == 1


@pytest.mark.asyncio
async def test_function_uses_defining_lexical_resolver() -> None:
    """Call-site values cannot replace names captured from definition scope."""
    function = await evaluate(
        parse_expression("(x) -> x + outer"),
        {"outer": 40},
    )
    result = await evaluate(
        parse_expression("function(2)"),
        {"function": function, "outer": 100},
    )
    assert result == 42


@pytest.mark.asyncio
async def test_all_parameter_kinds_bind_to_local_values() -> None:
    """Positional, defaults, variadics, and keyword-only values bind together."""
    source = "(a, b=2, *args, option=3, **kwargs) -> [a, b, args, option, kwargs]"
    function = await evaluate(parse_expression(source))
    result = await evaluate(
        parse_expression("function(1, *items, option=5, extra=6)"),
        {"function": function, "items": [3, 4]},
    )
    assert result == [1, 3, (4,), 5, {"extra": 6}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call_source",
    [
        "function()",
        "function(1, 2)",
        "function(1, a=2)",
        "function(other=1)",
    ],
)
async def test_invalid_argument_bindings_raise_public_error(call_source: str) -> None:
    """Invalid bindings are structured before body evaluation begins."""
    function = await evaluate(parse_expression("(a) -> a"))
    with pytest.raises(LclEvaluationError) as caught:
        await evaluate(parse_expression(call_source), {"function": function})
    assert isinstance(caught.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_concurrent_calls_have_independent_recursion_state() -> None:
    """Separate tasks may invoke the same function value concurrently."""

    async def delayed(value: int) -> int:
        await asyncio.sleep(0)
        return value

    function = await evaluate(
        parse_expression("(value) -> delayed(value)"),
        {"delayed": delayed},
    )
    first = evaluate(parse_expression("function(1)"), {"function": function})
    second = evaluate(parse_expression("function(2)"), {"function": function})
    assert list(await asyncio.gather(first, second)) == [1, 2]


Y_SOURCE = (
    "(f) -> ((x) -> f((value) -> x(x)(value)))"
    "((x) -> f((value) -> x(x)(value)))"
)
Z_SOURCE = (
    "(f) -> ((x) -> f((*args) -> x(x)(*args)))"
    "((x) -> f((*args) -> x(x)(*args)))"
)


async def _recursive_numeric_results(combinator_source: str, name: str) -> tuple[int, int]:
    """Define factorial and Fibonacci with one named LCL fixed-point value."""
    fixed_point = await evaluate(parse_expression(combinator_source))
    factorial = await evaluate(
        parse_expression(f"{name}((again) -> (n) -> 1 if n <= 1 else n * again(n - 1))"),
        {name: fixed_point},
    )
    fibonacci = await evaluate(
        parse_expression(
            f"{name}((again) -> (n) -> n if n <= 1 else "
            "again(n - 1) + again(n - 2))"
        ),
        {name: fixed_point},
    )
    factorial_result = await evaluate(
        parse_expression("factorial(6)"), {"factorial": factorial}
    )
    fibonacci_result = await evaluate(parse_expression("fib(10)"), {"fib": fibonacci})
    return cast(int, factorial_result), cast(int, fibonacci_result)


@pytest.mark.asyncio
async def test_eta_expanded_y_defines_factorial_and_fibonacci() -> None:
    """Unary eta expansion makes Y usable with eager LCL evaluation."""
    assert await _recursive_numeric_results(Y_SOURCE, "Y") == (720, 55)


@pytest.mark.asyncio
async def test_variadic_z_defines_factorial_and_fibonacci() -> None:
    """Variadic eta expansion makes Z reusable by recursive LCL functions."""
    assert await _recursive_numeric_results(Z_SOURCE, "Z") == (720, 55)


@pytest.mark.asyncio
async def test_recursive_quicksort_is_a_separate_lcl_program() -> None:
    """Quicksort recursively partitions duplicates and negative integers."""
    fixed_point = await evaluate(parse_expression(Z_SOURCE))
    quicksort = await evaluate(
        parse_expression(
            "Z((again) -> (items) -> [] if not items else "
            "again([item for item in items[1:] if item < items[0]]) + "
            "[items[0]] + "
            "again([item for item in items[1:] if item >= items[0]]))"
        ),
        {"Z": fixed_point},
    )
    assert await evaluate(
        parse_expression("sort(values)"),
        {"sort": quicksort, "values": [7, 2, 9, 2, -1, 5]},
    ) == [-1, 2, 2, 5, 7, 9]


@pytest.mark.asyncio
async def test_same_task_direct_recursion_is_rejected() -> None:
    """A function cannot directly re-enter itself through its captured resolver."""
    values: dict[str, object] = {}
    function = await evaluate(parse_expression("() -> self()"), values)
    values["self"] = function
    call = cast(Callable[..., Awaitable[object]], function)
    with pytest.raises(LclEvaluationError, match="recursion"):
        await call()
