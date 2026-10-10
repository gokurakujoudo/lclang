"""Day filters.

Defines ``filter_day_type``, ``OnlyBusinessDayBDCalendar``, ``OnlyHolidayBDCalendar``.
"""

from __future__ import annotations

from collections.abc import Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar
from lclang.utils.calendar.transformations.calendar_dependency import (
    dependency_day_type,
    direct_dependency_ids,
)


@guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
async def filter_day_type(calendar: BDCalendar, d: date, target: DayType) -> DayType:
    """Retain one defined category and make other classifications undefined.

    :param calendar: Source calendar.
    :param d: Date to classify.
    :param target: BusinessDay or Holiday category retained by the filter.
    :returns: Target category when matched, otherwise Undefined.
    :raises CalendarLogicException: If dependency classification fails unexpectedly.
    """
    value = await dependency_day_type(calendar, d)
    return target if value is target else DayType.Undefined


@guard_constructor(LclValidationError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
@final
class OnlyBusinessDayBDCalendar(FunctionalBDCalendar):
    """Retain only a base calendar's business dates.

    :param base_calendar: Calendar whose holidays become undefined.
    """

    __slots__ = ("base_calendar",)

    def __init__(self, base_calendar: BDCalendar) -> None:
        """Create a sparse business-day filter.

        :param base_calendar: Calendar whose holidays become undefined.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        super().__init__(CalendarID(f"{base_calendar!r}.business_days()"))

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Retain only business-day values.

        :param d: Date to classify.
        :returns: Business day or undefined.
        """
        return await filter_day_type(self.base_calendar, d, DayType.BusinessDay)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the filtered calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))

    @guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    def business_days(self) -> OnlyBusinessDayBDCalendar:
        """Return this already-filtered calendar.

        :returns: This calendar instance.
        """
        return self


@guard_constructor(LclValidationError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
@final
class OnlyHolidayBDCalendar(FunctionalBDCalendar):
    """Retain only a base calendar's holidays.

    :param base_calendar: Calendar whose business days become undefined.
    """

    __slots__ = ("base_calendar",)

    def __init__(self, base_calendar: BDCalendar) -> None:
        """Create a sparse holiday filter.

        :param base_calendar: Calendar whose business days become undefined.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        super().__init__(CalendarID(f"{base_calendar!r}.holidays()"))

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Retain only holiday values.

        :param d: Date to classify.
        :returns: Holiday or undefined.
        """
        return await filter_day_type(self.base_calendar, d, DayType.Holiday)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the filtered calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))

    @guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    def holidays(self) -> OnlyHolidayBDCalendar:
        """Return this already-filtered calendar.

        :returns: This calendar instance.
        """
        return self
