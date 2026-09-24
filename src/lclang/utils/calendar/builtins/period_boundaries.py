"""Period boundaries."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class BeginOfMonthCalendar(FunctionalBDCalendar):
    """Classify the first calendar day of every month as business."""

    async def get_day_type(self, d: date) -> DayType:
        """Classify the first day of a month.

        :param d: Date to classify.
        :returns: Business day on day one, otherwise holiday.
        """
        return DayType.BusinessDay if d.day == 1 else DayType.Holiday


# Singleton calendar for first calendar days of months.
# Unitless singleton IDs below follow the builtin calendar registry. Gregorian month and year
# boundaries define the selected dates; shared instances preserve canonical IDs, repr and
# identity without configurable boundary state.
BEGIN_OF_MONTHS = BeginOfMonthCalendar(CalendarID("BEGIN_OF_MONTHS"))


@final
class EndOfMonthCalendar(FunctionalBDCalendar):
    """Classify the last calendar day of every month as business."""

    async def get_day_type(self, d: date) -> DayType:
        """Classify the last day of a month.

        :param d: Date to classify.
        :returns: Business day on the month end, otherwise holiday.
        """
        return DayType.BusinessDay if d.day == monthrange(d.year, d.month)[1] else DayType.Holiday


# Singleton calendar for last calendar days of months.
END_OF_MONTHS = EndOfMonthCalendar(CalendarID("END_OF_MONTHS"))


@final
class BeginOfYearCalendar(FunctionalBDCalendar):
    """Classify January first as business."""

    async def get_day_type(self, d: date) -> DayType:
        """Classify the first day of a year.

        :param d: Date to classify.
        :returns: Business day on January first, otherwise holiday.
        """
        return DayType.BusinessDay if (d.month, d.day) == (1, 1) else DayType.Holiday


# Singleton calendar for first calendar days of years.
BEGIN_OF_YEARS = BeginOfYearCalendar(CalendarID("BEGIN_OF_YEARS"))


@final
class EndOfYearCalendar(FunctionalBDCalendar):
    """Classify December thirty-first as business."""

    async def get_day_type(self, d: date) -> DayType:
        """Classify the last day of a year.

        :param d: Date to classify.
        :returns: Business day on December thirty-first, otherwise holiday.
        """
        return DayType.BusinessDay if (d.month, d.day) == (12, 31) else DayType.Holiday


# Singleton calendar for last calendar days of years.
END_OF_YEARS = EndOfYearCalendar(CalendarID("END_OF_YEARS"))
