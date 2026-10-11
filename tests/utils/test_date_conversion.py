"""Behavioural tests for locale-independent Python date conversion."""

from datetime import date

import pytest

from lclang.error import LclValidationError
from lclang.utils.date_conversion import parse_ymd, to_ymd


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
    with pytest.raises(LclValidationError):
        parse_ymd(value)


def test_date_helpers_reject_wrong_types() -> None:
    """Helper boundaries fail before coercing unrelated host values."""
    with pytest.raises(LclValidationError):
        parse_ymd(20240229)  # type: ignore[arg-type]
    with pytest.raises(LclValidationError):
        to_ymd("20240229")  # type: ignore[arg-type]
