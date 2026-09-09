"""Day filters."""

from __future__ import annotations

from collections.abc import Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type, direct_dependency_ids
from lclang.utils.calendar.types import CalendarID, DayType


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

    async def get_day_type(self, d: date) -> DayType:
        """Retain only business-day values.

        :param d: Date to classify.
        :returns: Business day or undefined.
        """
        return await filter_day_type(self.base_calendar, d, DayType.BusinessDay)

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the filtered calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))

    def business_days(self) -> OnlyBusinessDayBDCalendar:
        """Return this already-filtered calendar.

        :returns: This calendar instance.
        """
        return self





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

    async def get_day_type(self, d: date) -> DayType:
        """Retain only holiday values.

        :param d: Date to classify.
        :returns: Holiday or undefined.
        """
        return await filter_day_type(self.base_calendar, d, DayType.Holiday)

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the filtered calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))

    def holidays(self) -> OnlyHolidayBDCalendar:
        """Return this already-filtered calendar.

        :returns: This calendar instance.
        """
        return self
