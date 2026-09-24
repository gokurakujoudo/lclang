"""Calendar callable calendar contracts."""

from datetime import date

import pytest

from lclang.utils.calendar import (
    CalendarID,
    CalendarLogicException,
    DayType,
    def_functional_calendar,
)


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
