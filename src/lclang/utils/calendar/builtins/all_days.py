"""Calendar that treats every supported date as business."""

from datetime import date
from typing import final

from lclang.error import LclUtilityError
from lclang.error.boundary import guard_async_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class AllDaysBDCalendar(FunctionalBDCalendar):
    """Classify every Gregorian date as a business day."""

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_716)
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
