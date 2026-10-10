"""Behavioural contracts for unnamed Frame expressions."""

from typing import Any, cast

import pytest

from lclang.error import LclClosedFrameError, LclSyntaxError, LclValidationError
from lclang.lang import define_frame, define_module, parse_expression


@pytest.mark.asyncio
async def test_frame_evaluate_is_uncached_but_reuses_named_snapshots() -> None:
    """Each root runs anew while named dependencies keep Frame caching."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return 21

    module = define_module("app", {"A.value": "produce()"})
    async with define_frame(module, preset={"produce": produce}) as frame:
        assert await frame.evaluate("A.value * 2") == 42
        assert await frame.evaluate("A.value * 2") == 42
        assert calls == 1
        assert frame.inspect_variable("<expr>").current_exception is not None


@pytest.mark.asyncio
async def test_frame_evaluate_sets_and_captures_lhs_owner() -> None:
    """Unnamed roots and closures use the stable expression owner label."""
    async with define_frame() as frame:
        assert await frame.evaluate("lhs()") == "<expr>"
        function = cast(Any, await frame.evaluate("() -> lhs()"))
        assert await function() == "<expr>"


@pytest.mark.asyncio
async def test_frame_evaluate_validates_input_and_lifecycle() -> None:
    """The convenience boundary accepts source text only on an open Frame."""
    frame = define_frame()
    with pytest.raises(LclValidationError, match="string"):
        await frame.evaluate(cast(Any, parse_expression("1")))
    with pytest.raises(LclSyntaxError):
        await frame.evaluate("1 +")
    await frame.close()
    with pytest.raises(LclClosedFrameError):
        await frame.evaluate("1")
