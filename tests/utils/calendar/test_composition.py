"""Behavioral tests for transformations, builtins, and factories."""

from datetime import date

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BEGIN_OF_MONTHS,
    END_OF_MONTHS,
    FRIDAYS,
    MONDAYS,
    CalendarID,
    CalendarLogicException,
    DayType,
    at,
    def_functional_calendar,
    nth_business_day_of_month,
    nth_day_of_month,
    range_end_days,
    range_start_days,
)


@pytest.mark.asyncio
async def test_transformation_truth_tables_and_canonical_representations() -> None:
    """Composition follows three-state precedence and canonicalizes sets."""
    monday = date(2024, 1, 1)
    tuesday = date(2024, 1, 2)
    sparse = at(monday)
    holiday = nth_day_of_month(2)
    union = holiday + sparse
    assert repr(sparse + holiday) == repr(union)
    assert await union.get_day_type(monday) is DayType.BusinessDay
    assert await union.get_day_type(tuesday) is DayType.BusinessDay
    intersection = sparse & holiday
    assert await intersection.get_day_type(monday) is DayType.Holiday
    assert await intersection.get_day_type(tuesday) is DayType.BusinessDay
    subtraction = ALL_DAYS - holiday
    assert await subtraction.get_day_type(tuesday) is DayType.Holiday
    assert await (sparse >> holiday).get_day_type(tuesday) is DayType.BusinessDay
    assert await (~holiday).get_day_type(tuesday) is DayType.Holiday
    assert ~~holiday is holiday
    assert sparse.business_days() is sparse
    assert holiday.business_days() is holiday
    assert await holiday.holidays().get_day_type(monday) is DayType.Holiday


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


@pytest.mark.asyncio
async def test_date_selection_factories_cover_signed_positions_and_ranges() -> None:
    """Factory calendars handle parsing, negative positions, and range edges."""
    explicit = at("20240101", 20240103, date(2024, 1, 2), "20240101")
    assert repr(explicit) == "at(20240101, 20240102, 20240103)"
    selector = nth_day_of_month(-1, 1, -1)
    assert await selector.get_day_type(date(2024, 2, 29)) is DayType.BusinessDay
    assert await selector.get_day_type(date(2024, 2, 2)) is DayType.Holiday
    assert nth_business_day_of_month(ALL_DAYS, 1) == nth_day_of_month(1)
    weekdays = nth_business_day_of_month(ALL_WEEKDAYS, 1, -1)
    assert await weekdays.get_day_type(date(2024, 6, 3)) is DayType.BusinessDay
    run = at("20240102", "20240103", "20240105")
    assert await range_start_days(run).get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
    assert await range_end_days(run).get_day_type(date(2024, 1, 3)) is DayType.BusinessDay
    with pytest.raises(ValueError):
        nth_day_of_month(0)
    with pytest.raises(TypeError):
        at(object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_callable_factory_supports_async_values_and_wraps_failures() -> None:
    """Callable calendars validate asynchronous classification and dependency values."""
    async def classify(d: date) -> DayType:
        return DayType.BusinessDay if d.day == 1 else DayType.Holiday

    calendar = def_functional_calendar(
        CalendarID("CALLABLE"),
        classify,
        lambda: frozenset((CalendarID("BASE"),)),
    )
    assert await calendar.get_day_type(date(2024, 1, 1)) is DayType.BusinessDay
    assert await calendar.get_dependency_ids() == {CalendarID("BASE")}

    def broken(d: date) -> DayType:
        raise RuntimeError(str(d))

    failed = def_functional_calendar(CalendarID("FAILED"), broken)
    with pytest.raises(CalendarLogicException) as failure:
        await failed.get_day_type(date(2024, 1, 1))
    assert isinstance(failure.value.__cause__, RuntimeError)
