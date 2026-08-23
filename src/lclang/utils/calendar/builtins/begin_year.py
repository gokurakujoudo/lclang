"""First-calendar-day-of-year calendar."""

from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


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

