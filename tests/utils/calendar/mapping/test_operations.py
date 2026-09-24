"""Behavioral tests for calendar date mappings."""

from datetime import date
from typing import cast

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    SELF_CALENDAR,
    BDCalendar,
    BDCalendarMapping,
    CalendarID,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    DayType,
    ShiftNDaysMapOperation,
    UnappliedCalendarOperationException,
    at,
)


class PointDomainCalendar(BDCalendar):
    """Define one point while rejecting strict navigation outside its domain."""

    def __init__(self, point: date) -> None:
        """Create a point-domain test calendar."""
        super().__init__(CalendarID("POINT_DOMAIN"))
        self.point = point

    async def get_day_type(self, d: date) -> DayType:
        return DayType.BusinessDay if d == self.point else DayType.Undefined

    async def next_bd(self, d: date) -> date:
        raise DateOperationOutOfScopeException(d, self)

    async def prev_bd(self, d: date) -> date:
        raise DateOperationOutOfScopeException(d, self)

    async def gen_year(self, year: int) -> dict[date, DayType]:
        return {self.point: DayType.BusinessDay} if year == self.point.year else {}


class BrokenNavigationCalendar(BDCalendar):
    """Raise an unexpected error from strict date navigation."""

    def __init__(self) -> None:
        """Create the broken calendar."""
        super().__init__(CalendarID("BROKEN_NAVIGATION"))

    async def get_day_type(self, d: date) -> DayType:
        return DayType.Undefined

    async def next_bd(self, d: date) -> date:
        raise RuntimeError("next failed")

    async def prev_bd(self, d: date) -> date:
        raise RuntimeError("previous failed")

    async def gen_year(self, year: int) -> dict[date, DayType]:
        return {}


class InvalidNavigationCalendar(BrokenNavigationCalendar):
    """Return a non-date from strict forward navigation."""

    async def next_bd(self, d: date) -> date:
        return cast(date, "not-a-date")


@pytest.mark.asyncio
async def test_primitive_mappings_shift_cache_and_reverse_ranges() -> None:
    """Primitive adjustment supports cache reuse and many-to-one reverse lookup."""
    saturday = date(2024, 1, 6)
    mapping = ALL_DAYS.map_this_or_next(ALL_WEEKDAYS)
    assert await mapping.map_date(saturday) == date(2024, 1, 8)
    assert await mapping.map_date(saturday) == date(2024, 1, 8)
    assert mapping.mapped_dates[saturday] == date(2024, 1, 8)
    assert await mapping.map_date_reverse(date(2024, 1, 8)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )
    assert len(mapping.operations[0].mapped_dates) < 40
    assert await ALL_DAYS.shift_n_days(1, ALL_WEEKDAYS).map_date(saturday) == date(2024, 1, 8)
    assert await ALL_DAYS.shift_n_days(-1, ALL_WEEKDAYS).map_date(saturday) == date(2024, 1, 5)
    assert await ALL_DAYS.shift_n_days(0, ALL_WEEKDAYS).map_date(saturday) == date(2024, 1, 8)
    with pytest.raises(ValueError):
        ShiftNDaysMapOperation(101, ALL_DAYS)
    point = date(2024, 1, 8)
    assert await ALL_DAYS.map_this_or_next(PointDomainCalendar(point)).map_date_reverse(point) == (
        point,
        point,
    )


@pytest.mark.asyncio
async def test_unapplied_and_composed_mappings_remain_immutable() -> None:
    """Applying and extending a mapping creates bound copies without mutation."""
    operation = ShiftNDaysMapOperation(1, SELF_CALENDAR)
    mapping = BDCalendarMapping(operations=(operation,))
    with pytest.raises(UnappliedCalendarOperationException):
        await mapping.map_date(date(2024, 1, 1))
    applied = await mapping.apply(ALL_DAYS)
    extended = applied.shift_n_days(1, ALL_DAYS)
    assert mapping.has_applied is False
    assert applied.has_applied is True
    assert len(applied.operations) == 1 and len(extended.operations) == 2
    assert await extended.map_date(date(2024, 1, 1)) == date(2024, 1, 3)
    with pytest.raises(AttributeError):
        operation.base_calendar = ALL_DAYS
    with pytest.raises(AttributeError):
        operation.n = 2
    with pytest.raises(AttributeError):
        mapping.operations = ()


@pytest.mark.asyncio
async def test_composite_reverse_processes_each_operation_backward() -> None:
    """Reverse composition expands primitive preimages in reverse apply order."""
    mapping = ALL_DAYS.map_this_or_next(ALL_WEEKDAYS).shift_n_days(1, ALL_WEEKDAYS)
    assert await mapping.map_date_reverse(date(2024, 1, 9)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )
    assert mapping.mapped_dates == {}
    assert all(len(operation.mapped_dates) < 80 for operation in mapping.operations)
    repeated = ALL_DAYS.map_this_or_next(ALL_DAYS).map_this_or_next(ALL_WEEKDAYS)
    assert await repeated.map_date_reverse(date(2024, 1, 8)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )


@pytest.mark.asyncio
async def test_mapping_as_calendar_uses_source_business_dates() -> None:
    """Mapped calendar targets require at least one source business day."""
    mapping = ALL_WEEKDAYS.map_this_or_next(ALL_WEEKDAYS)
    calendar = await mapping.as_calendar(CalendarID("MAPPED"))
    assert await calendar.get_day_type(date(2024, 1, 8)) is DayType.BusinessDay
    assert await calendar.get_day_type(date(2024, 1, 7)) is DayType.Holiday
    assert await calendar.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    finite = ALL_DAYS.map_this_or_next(at(date.min))
    with pytest.raises(DateOperationOutOfScopeException):
        await finite.map_date_reverse(date.max)


@pytest.mark.asyncio
async def test_mapping_wraps_unexpected_navigation_failures_with_the_dependency() -> None:
    """Primitive dependency failures retain their cause and calendar identity."""
    broken = BrokenNavigationCalendar()
    mappings = (
        ALL_DAYS.map_this_or_next(broken),
        ALL_DAYS.map_this_or_prev(broken),
        ALL_DAYS.shift_n_days(1, broken),
    )
    for mapping in mappings:
        with pytest.raises(CalendarLogicException) as failure:
            await mapping.map_date(date(2024, 1, 1))
        assert failure.value.calendar_id == broken.calendar_id
        assert isinstance(failure.value.__cause__, RuntimeError)
    invalid = InvalidNavigationCalendar()
    with pytest.raises(CalendarLogicException) as invalid_failure:
        await ALL_DAYS.shift_n_days(1, invalid).map_date(date(2024, 1, 1))
    assert isinstance(invalid_failure.value.__cause__, TypeError)
