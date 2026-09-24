"""Calendar that treats every supported date as business."""

from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class AllDaysBDCalendar(FunctionalBDCalendar):
    """Classify every Gregorian date as a business day."""

    async def get_day_type(self, d: date) -> DayType:
        """Return business day for every date.

        :param d: Date to classify.
        :returns: Always :attr:`DayType.BusinessDay`.
        """
        return DayType.BusinessDay


# Singleton calendar that accepts every Gregorian date.
# Unitless singleton ID follows the builtin calendar registry. One shared ALL_DAYS object
# represents the total business-day identity and keeps equality, repr and identity stable.
ALL_DAYS = AllDaysBDCalendar(CalendarID("ALL_DAYS"))
