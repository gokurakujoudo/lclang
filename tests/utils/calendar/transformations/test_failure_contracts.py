"""Calendar failure contracts contracts."""

from datetime import date
from typing import cast

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BDCalendar,
    CalendarID,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    DayType,
    SubtractionBDCalendar,
    at,
    def_functional_calendar,
    nth_day_of_month,
)
from lclang.utils.calendar.transformations.logic import dependency_day_type, direct_dependency_ids
from lclang.utils.calendar.transformations.operands import canonical_calendars, ordered_calendars
from tests.utils.calendar.calendar_support import DomainFailureCalendar, RawFailureCalendar


@pytest.mark.asyncio
async def test_all_transformation_branches_and_dependency_wrapping() -> None:
    """Composition covers sparse truth tables, dependencies, and invalid operands."""
    d = date(2024, 1, 2)
    business = at(d)
    holiday = nth_day_of_month(1)
    undefined = at()
    assert await (business + holiday).get_day_type(date(2024, 1, 3)) is DayType.Holiday
    assert await (undefined & undefined).get_day_type(d) is DayType.Undefined
    intersection = business & ALL_DAYS
    assert await intersection.get_day_type(d) is DayType.BusinessDay
    assert await intersection.get_dependency_ids() == {
        CalendarID("ALL_DAYS"),
        business.calendar_id,
    }
    assert await (undefined >> at()).get_day_type(d) is DayType.Undefined
    assert await (undefined >> business).get_dependency_ids() == {
        undefined.calendar_id,
        business.calendar_id,
    }
    reverted = ~business
    assert await reverted.get_day_type(d) is DayType.Holiday
    assert await reverted.get_day_type(date(2024, 1, 3)) is DayType.Undefined
    assert await reverted.get_dependency_ids() == {business.calendar_id}
    assert await (~ALL_WEEKDAYS).get_day_type(date(2024, 1, 6)) is DayType.BusinessDay
    only_business = ALL_WEEKDAYS.business_days()
    assert await only_business.get_day_type(d) is DayType.BusinessDay
    assert only_business.business_days() is only_business
    assert await only_business.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    only_holiday = ALL_WEEKDAYS.holidays()
    assert only_holiday.holidays() is only_holiday
    assert await only_holiday.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}

    subtraction = SubtractionBDCalendar(business, (undefined,))
    assert await subtraction.get_day_type(date(2024, 1, 3)) is DayType.Undefined
    holiday_base = SubtractionBDCalendar(holiday, (business,))
    assert await holiday_base.get_day_type(d) is DayType.Holiday
    assert await subtraction.get_day_type(d) is DayType.BusinessDay
    flattened = subtraction.minus(ALL_DAYS)
    assert await flattened.get_day_type(d) is DayType.Holiday
    assert business.calendar_id in await flattened.get_dependency_ids()
    with pytest.raises(TypeError):
        SubtractionBDCalendar(cast(BDCalendar, object()), (business,))
    for normalizer in (canonical_calendars, ordered_calendars):
        with pytest.raises(TypeError):
            normalizer((cast(BDCalendar, object()),))
        with pytest.raises(ValueError):
            normalizer(())
    assert await direct_dependency_ids((business,)) == {business.calendar_id}
    with pytest.raises(DateOperationOutOfScopeException):
        await dependency_day_type(DomainFailureCalendar(CalendarID("DOMAIN2")), d)
    with pytest.raises(CalendarLogicException) as raw_failure:
        await dependency_day_type(RawFailureCalendar(CalendarID("RAW")), d)
    assert isinstance(raw_failure.value.__cause__, RuntimeError)
    assert (undefined >> business).base_fallback_calendars() == (undefined, business)

    async def invalid(d: date) -> DayType:
        return cast(DayType, "bad")

    with pytest.raises(CalendarLogicException):
        await dependency_day_type(def_functional_calendar(CalendarID("INVALID"), invalid), d)
