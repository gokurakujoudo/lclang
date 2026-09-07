"""Calendar failure contracts contracts."""

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
    CalendarMapBDCalendar,
    DateOperationOutOfScopeException,
    ShiftNDaysMapOperation,
    ThisOrNextMapOperation,
    ThisOrPrevMapOperation,
    UnappliedCalendarOperationException,
    at,
)


@pytest.mark.asyncio
async def test_primitive_and_composite_mapping_rainy_contracts() -> None:
    """Mappings cover sentinel, binding, reverse, cache, and displacement failures."""
    with pytest.raises(TypeError):
        ThisOrNextMapOperation(cast(BDCalendar, object()))
    operation = ThisOrNextMapOperation(ALL_WEEKDAYS)
    assert await operation.map_date(date(2024, 1, 7)) == date(2024, 1, 8)
    assert await operation.map_date(date(2024, 1, 7)) == date(2024, 1, 8)
    assert await operation.map_date_reverse(date(2024, 1, 8)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )
    assert await operation.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert await ThisOrNextMapOperation(ALL_DAYS).map_date_reverse(date.min) == (
        date.min,
        date.min,
    )
    assert repr(operation.with_base_calendar(ALL_DAYS)) == ".map_this_or_next(ALL_DAYS)"
    sentinel_operation = ThisOrNextMapOperation()
    assert await sentinel_operation.get_dependency_ids() == set()
    with pytest.raises(UnappliedCalendarOperationException):
        await sentinel_operation.map_date(date.today())

    previous = ThisOrPrevMapOperation(ALL_WEEKDAYS)
    sunday = date(2024, 1, 7)
    assert await previous.map_date(sunday) == date(2024, 1, 5)
    assert await previous.map_date(sunday) == date(2024, 1, 5)
    assert repr(previous.with_base_calendar(ALL_DAYS)) == ".map_this_or_prev(ALL_DAYS)"
    far = ThisOrNextMapOperation(at(date(2024, 5, 1)))
    with pytest.raises(DateOperationOutOfScopeException):
        await far.map_date(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await far.map_date_reverse(date(2024, 1, 1))

    for value in (True, 1.5):
        with pytest.raises(TypeError):
            ShiftNDaysMapOperation(cast(int, value), ALL_DAYS)
    shift = ShiftNDaysMapOperation(1, ALL_DAYS)
    assert await shift.map_date(date(2024, 1, 1)) == date(2024, 1, 2)
    assert await shift.map_date(date(2024, 1, 1)) == date(2024, 1, 2)
    assert repr(shift.with_base_calendar(ALL_WEEKDAYS)).startswith(".shift_n_days")
    with pytest.raises(TypeError):
        BDCalendarMapping(operations=(cast(ShiftNDaysMapOperation, object()),))
    unapplied = BDCalendarMapping()
    assert await unapplied.get_dependency_ids() == set()
    with pytest.raises(UnappliedCalendarOperationException):
        await unapplied.map_date_reverse(date.today())
    with pytest.raises(UnappliedCalendarOperationException):
        await unapplied.as_calendar()
    applied = await unapplied.apply(ALL_DAYS)
    assert await applied.map_date(date.today()) == date.today()
    assert await applied.map_date_reverse(date.today()) == (date.today(), date.today())
    assert applied.map_this_or_next().map_this_or_prev().shift_n_days(0).has_applied
    result = await applied.as_calendar()
    assert result.calendar_id == CalendarID("ALL_DAYS.as_calendar()")
    with pytest.raises(ValueError):
        CalendarMapBDCalendar(CalendarID("BAD"), unapplied)
    for method in (
        SELF_CALENDAR.get_day_type(date.today()),
        SELF_CALENDAR.next_bd(date.today()),
        SELF_CALENDAR.prev_bd(date.today()),
        SELF_CALENDAR.gen_year(2024),
    ):
        with pytest.raises(UnappliedCalendarOperationException):
            await method
