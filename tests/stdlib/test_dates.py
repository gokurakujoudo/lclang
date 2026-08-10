"""Behavioural tests for locale-independent LCL calendar builtins."""

from datetime import date

import pytest

import lclang
from lclang.stdlib.dates import parse_ymd, to_ymd


def test_date_helpers_round_trip_leap_day_and_early_year() -> None:
    """Strict ASCII dates parse and format with stable four-digit years."""
    assert parse_ymd("20240229") == date(2024, 2, 29)
    assert to_ymd(date(2024, 2, 29)) == "20240229"
    assert to_ymd(date(1, 1, 2)) == "00010102"


@pytest.mark.parametrize(
    "value",
    ["2024-02-29", "2024022", "２０２４０２２９", "20230229", "20241301"],
)
def test_parse_ymd_rejects_malformed_or_impossible_dates(value: str) -> None:
    """Malformed width/alphabet and Gregorian calendar errors stay explicit."""
    with pytest.raises(ValueError):
        parse_ymd(value)


def test_date_helpers_reject_wrong_types() -> None:
    """Helper boundaries fail before coercing unrelated host values."""
    with pytest.raises(TypeError):
        parse_ymd(20240229)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_ymd("20240229")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_date_helpers_are_available_through_lcl_builtins() -> None:
    """Canonical Frames parse and format dates through ordinary definitions."""
    frame = lclang.define_frame(
        lclang.define_module(
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
