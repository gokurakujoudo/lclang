"""Behavioral tests mirroring :mod:`lclang.stdlib.recursion`."""

from collections.abc import Awaitable, Callable

import pytest

import lclang
from lclang.stdlib import recursive


@pytest.mark.asyncio
async def test_recursive_builtin_evaluates_factorial_in_default_frame() -> None:
    """A normal LCL definition uses the builtin without supplying a combinator."""
    module = lclang.define_module(
        "factorial",
        {
            "factorial": (
                "recursive((again) -> (n) -> "
                "1 if n <= 1 else n * again(n - 1))"
            ),
            "result": "factorial(6)",
        },
    )
    frame = lclang.define_frame(module)
    try:
        assert await frame.get("result") == 720
        function = await frame.get("factorial")
        assert repr(function) == (
            "Recursive Function: (again) -> (n) -> "
            "1 if n <= 1 else n * again(n - 1)"
        )
        rendered = repr(frame.inspect_variable("factorial"))
        assert "(Cached) Recursive Function: (again) -> (n) ->" in rendered
        assert "0x" not in rendered
        assert lclang.LCL_BUILTINS.values["recursive"] is recursive
        assert repr(lclang.LCL_BUILTINS.inspect_variable("recursive")).endswith(
            "(NativeProvided) Builtin Function: recursive"
        )
    finally:
        await frame.close()


@pytest.mark.asyncio
async def test_recursive_python_builder_repr_uses_function_name() -> None:
    """A Python builder is identified by name without an address-bearing repr."""

    def countdown_builder(
        again: Callable[[int], Awaitable[int]],
    ) -> Callable[[int], Awaitable[int]]:
        """Return one Python-authored recursive countdown step."""

        async def countdown(value: int) -> int:
            """Count recursive calls until zero.

            :param value: Non-negative remaining call count.
            :returns: Number of recursive calls including this step.
            """
            if value == 0:
                return 0
            return 1 + await again(value - 1)

        return countdown

    function = recursive(countdown_builder)
    assert repr(function) == "Recursive Function: countdown_builder"
    assert await function(3) == 3


@pytest.mark.asyncio
async def test_recursive_rejects_noncallable_builder_and_step() -> None:
    """Malformed builders fail at the earliest meaningful call boundary."""
    with pytest.raises(TypeError, match="builder must be callable"):
        recursive(1)  # type: ignore[arg-type]

    call = recursive(lambda again: 1)
    with pytest.raises(TypeError, match="must return a callable"):
        await call()


@pytest.mark.asyncio
async def test_recursive_builtin_sorts_composite_values() -> None:
    """The variadic fixed point supports recursive quicksort in ordinary LCL."""
    module = lclang.define_module(
        "quicksort",
        {
            "quicksort": (
                "recursive((again) -> (items) -> [] if not items else "
                "again([item for item in items[1:] if item < items[0]]) + "
                "[items[0]] + "
                "again([item for item in items[1:] if item >= items[0]]))"
            ),
            "result": "quicksort([7, 2, 9, 2, -1, 5])",
        },
    )
    frame = lclang.define_frame(module)
    try:
        assert await frame.get("result") == [-1, 2, 2, 5, 7, 9]
    finally:
        await frame.close()
