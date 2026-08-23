"""Sparse holiday filtering calendar."""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.types import CalendarID, DayType


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
        value = await dependency_day_type(self.base_calendar, d)
        return DayType.Holiday if value is DayType.Holiday else DayType.Undefined

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the filtered calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return frozenset((self.base_calendar.calendar_id,))

    def holidays(self) -> OnlyHolidayBDCalendar:
        """Return this already-filtered calendar.

        :returns: This calendar instance.
        """
        return self

