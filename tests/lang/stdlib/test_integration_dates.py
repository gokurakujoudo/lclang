"""Integration tests for Python date helpers exposed as LCL builtins."""

from datetime import date

import pytest

from lclang.lang import define_frame, define_module


@pytest.mark.asyncio
async def test_date_helpers_are_available_through_lcl_builtins() -> None:
    """Canonical Frames parse and format dates through ordinary definitions."""
    frame = define_frame(
        define_module(
            "dates",
            {
                "parsed": 'parse_ymd("20240229")',
                "formatted": "to_ymd(parsed)",
            },
        )
    )
    try:
        assert await frame.get("parsed") == date(2024, 2, 29)
        assert await frame.get("formatted") == "20240229"
    finally:
        await frame.close()
