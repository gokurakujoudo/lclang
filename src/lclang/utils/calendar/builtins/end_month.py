"""Last-calendar-day-of-month calendar."""

from calendar import monthrange
from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


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

