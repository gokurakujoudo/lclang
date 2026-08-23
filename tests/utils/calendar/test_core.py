"""Behavioral tests for calendar types and storage strategies."""

from datetime import date, timedelta
from typing import cast

import pytest

from lclang.utils.calendar import (
    MAX_BUSINESS_DAY_GAP_DAYS,
    CalendarID,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    DayType,
    ForwardStepBDCalendar,
    FunctionalBDCalendar,
    HardcodedBDCalendar,
    YearBatchBDCalendar,
)


class WeekendCalendar(FunctionalBDCalendar):
    """Simple total weekday classifier for strategy tests."""

    async def get_day_type(self, d: date) -> DayType:
        return DayType.BusinessDay if d.weekday() < 5 else DayType.Holiday


class BrokenCalendar(FunctionalBDCalendar):
    """Classifier returning an invalid value."""

    async def get_day_type(self, d: date) -> DayType:
        return "bad"  # type: ignore[return-value]


class EveryTwoDaysCalendar(ForwardStepBDCalendar):
    """Finite forward sequence used to verify sparse caching."""

    async def next_bd(self, d: date) -> date:
        if d >= date(2024, 1, 5):
            raise DateOperationOutOfScopeException(d, self)
        return d + timedelta(days=2)


class OneYearCalendar(YearBatchBDCalendar):
    """Year-batch strategy with one business date per year."""

    async def gen_year(self, year: int) -> dict[date, DayType]:
        return {date(year, 1, 2): DayType.BusinessDay}


@pytest.mark.asyncio
async def test_day_types_identity_and_hardcoded_navigation() -> None:
    """Static calendars normalize undefined values and navigate finite dates."""
    first = date(2024, 1, 2)
    last = date(2024, 2, 1)
    calendar = HardcodedBDCalendar(
        CalendarID("STATIC"),
        {
            first: DayType.BusinessDay,
            last: DayType.BusinessDay,
            date(2024, 1, 3): DayType.Undefined,
        },
    )
    equal = HardcodedBDCalendar(CalendarID("STATIC"), {})
    assert calendar == equal and hash(calendar) == hash(equal)
    assert tuple(DayType) == (DayType.BusinessDay, DayType.Holiday, DayType.Undefined)
    assert await calendar.get_day_type(date(2024, 1, 3)) is DayType.Undefined
    assert await calendar.next_bd(first) == last
    assert await calendar.prev_bd(last) == first
    assert await calendar.gen_year(2024) == {
        first: DayType.BusinessDay,
        last: DayType.BusinessDay,
    }
    with pytest.raises(AttributeError):
        calendar.calendar_id = CalendarID("OTHER")
    with pytest.raises(DateOperationOutOfScopeException):
        await calendar.next_bd(last)


@pytest.mark.asyncio
async def test_functional_strategy_caches_and_bounds_searches() -> None:
    """Functional traversal caches classifications and reports bounded failure."""
    calendar = WeekendCalendar(CalendarID("WEEKDAYS"))
    saturday = date(2024, 1, 6)
    assert await calendar.this_or_next_bd(saturday) == date(2024, 1, 8)
    assert await calendar.this_or_prev_bd(saturday) == date(2024, 1, 5)
    assert date(2024, 1, 8) in calendar.defined_dates
    assert len(await calendar.gen_year(2024)) == 366
    never = HardcodedBDCalendar(CalendarID("NEVER"), {})
    with pytest.raises(DateOperationOutOfScopeException):
        await never.next_bd(date.today())
    assert MAX_BUSINESS_DAY_GAP_DAYS == 1000
    with pytest.raises(CalendarLogicException) as failure:
        await BrokenCalendar(CalendarID("BROKEN")).next_bd(date(2024, 1, 1))
    assert isinstance(failure.value.__cause__, TypeError)


@pytest.mark.asyncio
async def test_forward_and_year_batch_strategies_cover_sparse_boundaries() -> None:
    """Forward and batch caches expose sparse dates without inventing holidays."""
    forward = EveryTwoDaysCalendar(CalendarID("FORWARD"), date(2024, 1, 1))
    assert await forward.get_day_type(date(2024, 1, 3)) is DayType.BusinessDay
    assert await forward.get_day_type(date(2024, 1, 4)) is DayType.Undefined
    assert await forward.prev_bd(date(2024, 1, 4)) == date(2024, 1, 3)
    assert await forward.gen_year(2024) == {
        date(2024, 1, 1): DayType.BusinessDay,
        date(2024, 1, 3): DayType.BusinessDay,
        date(2024, 1, 5): DayType.BusinessDay,
    }
    assert forward.fully_cached is True
    batch = OneYearCalendar(CalendarID("BATCH"))
    assert await batch.get_day_type(date(2025, 1, 2)) is DayType.BusinessDay
    assert await batch.next_bd(date(2025, 1, 1)) == date(2025, 1, 2)
    assert await batch.prev_bd(date(2025, 1, 3)) == date(2025, 1, 2)
    assert 2025 in batch.loaded_year_batches
    with pytest.raises(TypeError):
        cast(dict[date, DayType], batch.loaded_year_batches[2025])[
            date(2025, 1, 2)
        ] = DayType.Holiday


@pytest.mark.parametrize("year", (0, 10000, True))
@pytest.mark.asyncio
async def test_year_generation_rejects_values_outside_datetime_range(year: int) -> None:
    """Every strategy rejects unsupported Gregorian years consistently."""
    calendar = HardcodedBDCalendar(CalendarID("EMPTY"), {})
    with pytest.raises(ValueError):
        await calendar.gen_year(year)
