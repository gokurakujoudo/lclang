"""Last-calendar-day-of-year calendar."""

from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


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

