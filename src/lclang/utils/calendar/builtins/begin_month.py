"""First-calendar-day-of-month calendar."""

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
BEGIN_OF_MONTHS = BeginOfMonthCalendar(CalendarID("BEGIN_OF_MONTHS"))

