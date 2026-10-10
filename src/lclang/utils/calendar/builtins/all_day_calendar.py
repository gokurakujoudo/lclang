"""Calendar that treats every supported date as business.

Defines ``AllDaysBDCalendar``.
"""

from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.operation_guard import guard_async_failure
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar


@final
class AllDaysBDCalendar(FunctionalBDCalendar):
    """Classify every Gregorian date as a business day."""

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E16_BUILTIN_CALENDAR_NATIVE_FAILURE)
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
