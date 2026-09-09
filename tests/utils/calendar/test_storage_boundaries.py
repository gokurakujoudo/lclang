"""Calendar storage boundaries contracts."""

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
    HardcodedBDCalendar,
    def_functional_calendar,
)
from tests.utils.calendar.calendar_support import (
    DomainFailureCalendar,
    InvalidBatchCalendar,
    InvalidForwardCalendar,
    SimpleForwardCalendar,
)


@pytest.mark.asyncio
async def test_core_validation_and_boundary_search_failures() -> None:
    """Core strategies reject invalid identity, mapping, and date boundaries."""
    with pytest.raises(TypeError):
        HardcodedBDCalendar(cast(CalendarID, 1), {})
    with pytest.raises(ValueError):
        HardcodedBDCalendar(CalendarID(""), {})
    with pytest.raises(TypeError):
        HardcodedBDCalendar(CalendarID("BAD"), {cast(date, "bad"): DayType.Holiday})
    with pytest.raises(TypeError):
        HardcodedBDCalendar(CalendarID("BAD"), {date.today(): cast(DayType, "bad")})
    empty = HardcodedBDCalendar(CalendarID("EMPTY"), {})
    with pytest.raises(DateOperationOutOfScopeException):
        await empty.prev_bd(date.today())
    assert await empty.business_days().get_day_type(date.today()) is DayType.Undefined
    total = DomainFailureCalendar(CalendarID("DOMAIN"))
    with pytest.raises(DateOperationOutOfScopeException):
        await total.cached_day_type(date.today())
    with pytest.raises(DateOperationOutOfScopeException):
        await ALL_WEEKDAYS.next_bd(date.max)
    with pytest.raises(DateOperationOutOfScopeException):
        await ALL_WEEKDAYS.prev_bd(date.min)
    assert await ALL_WEEKDAYS.map_this_or_prev().map_date(date(2024, 1, 7)) == date(
        2024, 1, 5
    )
    assert len(await ALL_DAYS.gen_year(9999)) == 365

    total_holiday = def_functional_calendar(
        CalendarID("TOTAL_HOLIDAY"), lambda d: DayType.Holiday
    )
    with pytest.raises(DateOperationOutOfScopeException):
        await total_holiday.next_bd(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await total_holiday.prev_bd(date(2024, 1, 1))


@pytest.mark.asyncio
async def test_forward_and_year_batch_reject_malformed_generation() -> None:
    """Generated strategies wrap unexpected results and preserve domain failures."""
    with pytest.raises(TypeError):
        SimpleForwardCalendar(CalendarID("BAD"), cast(date, "bad"))
    for result in (date(2024, 1, 1), "bad", RuntimeError("boom")):
        calendar = InvalidForwardCalendar(result)
        with pytest.raises(CalendarLogicException):
            await calendar.cache_through(date(2024, 1, 2))
    domain = InvalidForwardCalendar(DateOperationOutOfScopeException(date.today(), ALL_DAYS))
    await domain.cache_through(date(2024, 1, 2))
    assert domain.fully_cached
    with pytest.raises(DateOperationOutOfScopeException):
        await domain.prev_bd(date(2024, 1, 1))
    assert await domain.get_day_type(date(2023, 12, 31)) is DayType.Undefined
    assert await domain.gen_year(2023) == {}
    assert domain.defined_business_days == (date(2024, 1, 1),)
    propagated = InvalidForwardCalendar(CalendarCannotLoadException(CalendarID("LOAD")))
    with pytest.raises(CalendarCannotLoadException):
        await propagated.cache_through(date(2024, 1, 2))

    invalid_batches: tuple[object, ...] = (
        [],
        {date(2023, 1, 1): DayType.Holiday},
        {cast(date, "bad"): DayType.Holiday},
        {date(2024, 1, 1): cast(DayType, "bad")},
        RuntimeError("boom"),
    )
    for batch_result in invalid_batches:
        with pytest.raises(CalendarLogicException):
            await InvalidBatchCalendar(batch_result).loaded_year(2024)
    undefined = InvalidBatchCalendar({date(2024, 1, 1): DayType.Undefined})
    assert await undefined.loaded_year(2024) == {}
    assert await undefined.loaded_year(2024) is await undefined.loaded_year(2024)
    with pytest.raises(DateOperationOutOfScopeException):
        await undefined.next_bd(date.max)
    with pytest.raises(DateOperationOutOfScopeException):
        await undefined.prev_bd(date.min)
    propagated_batch = InvalidBatchCalendar(
        CalendarCannotLoadException(CalendarID("BATCH"))
    )
    with pytest.raises(CalendarCannotLoadException):
        await propagated_batch.loaded_year(2024)
    empty_batch = InvalidBatchCalendar({})
    with pytest.raises(DateOperationOutOfScopeException):
        await empty_batch.next_bd(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await empty_batch.prev_bd(date(2024, 1, 1))
