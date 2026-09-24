"""Single-weekday calendar and its seven singleton values."""

from datetime import date
from typing import final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class WeekdayBDCalendar(FunctionalBDCalendar):
    """Classify exactly one Python weekday as business.

    :param calendar_id: Unique calendar identifier.
    :param weekday: Python weekday number from zero through six.
    :raises ValueError: If *weekday* is outside zero through six.
    """

    __slots__ = ("weekday",)

    def __init__(self, calendar_id: CalendarID, weekday: int) -> None:
        """Create a single-weekday calendar.

        :param calendar_id: Unique calendar identifier.
        :param weekday: Python weekday number from zero through six.
        :returns: ``None``.
        :raises ValueError: If *weekday* is outside zero through six.
        """
        if not isinstance(weekday, int) or isinstance(weekday, bool) or not 0 <= weekday <= 6:
            raise ValueError("weekday must be between 0 and 6")
        self.weekday = weekday
        super().__init__(calendar_id)

    async def get_day_type(self, d: date) -> DayType:
        """Return business only on the selected weekday.

        :param d: Date to classify.
        :returns: Business day on the selected weekday, otherwise holiday.
        """
        return DayType.BusinessDay if d.weekday() == self.weekday else DayType.Holiday


# Singleton calendar that accepts Mondays.
# Unitless singleton IDs use the public weekday names. Python weekday indices run from Monday=0
# to Sunday=6; these seven shared instances cover exactly that Gregorian weekly cycle.
MONDAYS = WeekdayBDCalendar(CalendarID("MONDAYS"), 0)
# Singleton calendar that accepts Tuesdays.
TUESDAYS = WeekdayBDCalendar(CalendarID("TUESDAYS"), 1)
# Singleton calendar that accepts Wednesdays.
WEDNESDAYS = WeekdayBDCalendar(CalendarID("WEDNESDAYS"), 2)
# Singleton calendar that accepts Thursdays.
THURSDAYS = WeekdayBDCalendar(CalendarID("THURSDAYS"), 3)
# Singleton calendar that accepts Fridays.
FRIDAYS = WeekdayBDCalendar(CalendarID("FRIDAYS"), 4)
# Singleton calendar that accepts Saturdays.
SATURDAYS = WeekdayBDCalendar(CalendarID("SATURDAYS"), 5)
# Singleton calendar that accepts Sundays.
SUNDAYS = WeekdayBDCalendar(CalendarID("SUNDAYS"), 6)
