"""Calendar period boundaries contracts."""

import asyncio
from datetime import date

import pytest

from lclang.utils.calendar import (
    ALL_WEEKDAYS,
    BEGIN_OF_MONTHS,
    BEGIN_OF_YEARS,
    END_OF_MONTHS,
    END_OF_YEARS,
    FRIDAYS,
    MONDAYS,
    CalendarID,
    DayType,
    WeekdayBDCalendar,
)


@pytest.mark.asyncio
async def test_builtin_pattern_calendars_are_total() -> None:
    """Weekday and boundary singletons classify every nonmatch as holiday."""
    monday = date(2024, 1, 1)
    friday = date(2024, 1, 5)
    assert await ALL_WEEKDAYS.get_day_type(monday) is DayType.BusinessDay
    assert await MONDAYS.get_day_type(friday) is DayType.Holiday
    assert await FRIDAYS.get_day_type(friday) is DayType.BusinessDay
    assert await BEGIN_OF_MONTHS.get_day_type(monday) is DayType.BusinessDay
    assert await END_OF_MONTHS.get_day_type(date(2024, 2, 29)) is DayType.BusinessDay
    assert await END_OF_MONTHS.get_day_type(date(2024, 2, 28)) is DayType.Holiday


def test_remaining_total_builtin_and_weekday_validation() -> None:
    """Year-boundary builtins and weekday validation cover their complete contract."""
    assert asyncio.run(BEGIN_OF_YEARS.get_day_type(date(2024, 1, 1))) is DayType.BusinessDay
    assert asyncio.run(END_OF_YEARS.get_day_type(date(2024, 12, 31))) is DayType.BusinessDay
    with pytest.raises(ValueError):
        WeekdayBDCalendar(CalendarID("BAD"), 7)
