"""Snowflake construction, state ownership, and errors through canonical LCL."""

import asyncio
from unittest.mock import patch

import pytest

import lclang
from lclang.api import LCL_BUILTIN_VALUES
from lclang.utils import SnowflakeGenerator


@pytest.mark.asyncio
async def test_builtin_construction_cache_recalculation_and_composition() -> None:
    """LCL constructs the Python utility and caches IDs independently from its state."""
    assert LCL_BUILTIN_VALUES["SnowflakeGenerator"] is SnowflakeGenerator
    module = lclang.define_module(
        "snowflake",
        {
            "ids": "SnowflakeGenerator(worker_id, epoch_ms=0)",
            "request_id": "ids.next_id()",
            "label": 'f"request-{request_id}"',
            "batch": "[ids.next_id() for item in range(3)]",
        },
    )
    with patch("lclang.utils.snowflake.time_ns", return_value=1_000_000):
        async with lclang.define_frame(module, preset={"worker_id": 7}) as frame:
            first = (1 << 22) | (7 << 12)
            assert (
                await asyncio.gather(*(frame.get("request_id") for _ in range(10))) == [first] * 10
            )
            assert await frame.get("label") == f"request-{first}"
            await frame.recalculate("request_id")
            assert await frame.get("request_id") == first + 1
            assert await frame.get("label") == f"request-{first}"
            assert await frame.get("batch") == [first + 2, first + 3, first + 4]
            assert await frame.evaluate("ids.next_id()") == first + 5


@pytest.mark.asyncio
async def test_host_generator_is_shared_across_frames() -> None:
    """Separate request Frames borrow one worker's generator without resetting it."""
    generator = SnowflakeGenerator(2, epoch_ms=0)
    module = lclang.define_module("request", {"id": "ids.next_id()"})
    with patch("lclang.utils.snowflake.time_ns", return_value=0):
        async with (
            lclang.define_frame(module, preset={"ids": generator}) as first,
            lclang.define_frame(module, preset={"ids": generator}) as second,
        ):
            values = await asyncio.gather(first.get("id"), second.get("id"))
            assert list(values) == [8192, 8193]
        assert generator.next_id() == 8194


@pytest.mark.asyncio
async def test_lcl_reports_invalid_configuration_and_clock_rollback() -> None:
    """Constructor and generation failures remain visible at the language boundary."""
    errors: dict[str, object] = {"ValueError": ValueError, "RuntimeError": RuntimeError}
    async with lclang.define_frame(preset=errors) as frame:
        assert (
            await frame.evaluate("try: SnowflakeGenerator(1024) except ValueError: 'invalid'")
            == "invalid"
        )
        generator = SnowflakeGenerator(0, epoch_ms=0)
        frame.mixin({"ids": generator})
        with patch("lclang.utils.snowflake.time_ns", side_effect=[2_000_000, 1_000_000]):
            assert await frame.evaluate("ids.next_id()") == 2 << 22
            assert (
                await frame.evaluate("try: ids.next_id() except RuntimeError: 'rollback'")
                == "rollback"
            )
