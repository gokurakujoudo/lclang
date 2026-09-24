"""Monday-through-Friday calendar."""

from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class AllWeekdaysBDCalendar(FunctionalBDCalendar):
    """Classify Monday through Friday as business days."""

    async def get_day_type(self, d: date) -> DayType:
        """Classify a date from its ISO weekday.

        :param d: Date to classify.
        :returns: Business day on Monday through Friday, otherwise holiday.
        """
        return DayType.BusinessDay if d.weekday() < 5 else DayType.Holiday


# Singleton calendar that accepts Monday through Friday.
# Unitless singleton ID follows the builtin calendar registry. One shared ALL_WEEKDAYS object
# expresses the Monday-Friday policy and preserves canonical repr and identity.
ALL_WEEKDAYS = AllWeekdaysBDCalendar(CalendarID("ALL_WEEKDAYS"))
