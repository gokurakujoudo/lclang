"""Calendar date selection contracts."""

from collections.abc import Callable, Set
from datetime import date
from typing import cast

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    CalendarCannotLoadException,
    CalendarID,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    DayType,
    at,
    def_functional_calendar,
    nth_business_day_of_month,
    nth_day_of_month,
    range_end_days,
    range_start_days,
)


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
async def test_factories_cover_invalid_values_boundaries_and_cached_months() -> None:
    """Factories validate callbacks, dates, positions, and date-range edges."""
    for value in (-1, True, 123456789):
        with pytest.raises((TypeError, ValueError)):
            at(value)
    with pytest.raises(TypeError):
        nth_day_of_month(cast(int, "1"))
    with pytest.raises(ValueError):
        nth_day_of_month(32)
    selector = nth_day_of_month(31)
    assert await selector.get_day_type(date(2024, 2, 29)) is DayType.Holiday
    month = nth_business_day_of_month(ALL_WEEKDAYS, 1)
    assert await month.get_day_type(date(2024, 1, 1)) is DayType.BusinessDay
    assert await month.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await month.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert month.business_days() is month
    assert await range_start_days(ALL_DAYS).get_day_type(date.min) is DayType.BusinessDay
    assert await range_end_days(ALL_DAYS).get_day_type(date.max) is DayType.BusinessDay
    starts = range_start_days(ALL_WEEKDAYS)
    ends = range_end_days(ALL_WEEKDAYS)
    assert await starts.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await ends.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await starts.get_day_type(date(2024, 1, 6)) is DayType.Holiday
    assert await ends.get_day_type(date(2024, 1, 6)) is DayType.Holiday
    assert await starts.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert await ends.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}

    with pytest.raises(TypeError):
        def_functional_calendar(
            CalendarID("BAD"), cast(Callable[[date], DayType], 1)
        )
    with pytest.raises(TypeError):
        def_functional_calendar(
            CalendarID("BAD"),
            lambda d: DayType.BusinessDay,
            cast(Callable[[], Set[CalendarID]], 1),
        )
    no_dependencies = def_functional_calendar(
        CalendarID("NONE"), lambda d: DayType.BusinessDay
    )
    assert await no_dependencies.get_dependency_ids() == set()
    invalid_dependencies = def_functional_calendar(
        CalendarID("BAD_DEPS"),
        lambda d: DayType.BusinessDay,
        lambda: cast(Set[CalendarID], {CalendarID("")}),
    )
    with pytest.raises(CalendarLogicException):
        await invalid_dependencies.get_dependency_ids()

    def domain_classifier(d: date) -> DayType:
        raise DateOperationOutOfScopeException(d, ALL_DAYS)

    def domain_dependencies() -> Set[CalendarID]:
        raise CalendarCannotLoadException(CalendarID("DEPENDENCY"))

    callable_domain = def_functional_calendar(
        CalendarID("CALLABLE_DOMAIN"), domain_classifier, domain_dependencies
    )
    with pytest.raises(DateOperationOutOfScopeException):
        await callable_domain.get_day_type(date.today())
    with pytest.raises(CalendarCannotLoadException):
        await callable_domain.get_dependency_ids()
