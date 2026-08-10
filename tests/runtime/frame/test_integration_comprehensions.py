"""Frame integration tests for comprehension scope."""

import pytest

from lclang.lang.parser import parse_expression
from lclang.runtime import Frame, Module
from lclang.types import FrameId, ModuleName


@pytest.mark.asyncio
async def test_comprehension_target_does_not_resolve_or_replace_frame_name() -> None:
    """A loop target shadows a lazy definition only inside its comprehension."""
    x_calls = 0

    def produce_x() -> int:
        nonlocal x_calls
        x_calls += 1
        return 100

    module = Module(
        ModuleName("app"),
        {
            "x": parse_expression("produce_x()"),
            "y": parse_expression("[x + 1 for x in [1, 2, 3]]"),
        },
    )
    frame = Frame(module, FrameId("frame:1"), values={"produce_x": produce_x})

    assert await frame.get("y") == [2, 3, 4]
    assert x_calls == 0
    assert await frame.get("x") == 100
    assert x_calls == 1
