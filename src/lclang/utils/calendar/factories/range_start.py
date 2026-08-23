"""Contiguous business-range start factory."""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.helpers import safe_add_days
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.types import CalendarID, DayType


@final
class RangeStartDaysBDCalendar(FunctionalBDCalendar):
    """Select first dates of contiguous base-calendar business ranges.

    :param base_calendar: Calendar whose ranges are inspected.
    """

    __slots__ = ("base_calendar",)

    def __init__(self, base_calendar: BDCalendar) -> None:
        """Create a range-start selector.

        :param base_calendar: Calendar whose ranges are inspected.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        super().__init__(CalendarID(f"range_start_days({base_calendar!r})"))

    async def get_day_type(self, d: date) -> DayType:
        """Classify first dates of business ranges.

        :param d: Date to classify.
        :returns: Business on a range start, otherwise holiday.
        """
        if await dependency_day_type(self.base_calendar, d) is not DayType.BusinessDay:
            return DayType.Holiday
        previous = safe_add_days(d, -1)
        if previous is None:
            return DayType.BusinessDay
        value = await dependency_day_type(self.base_calendar, previous)
        return DayType.Holiday if value is DayType.BusinessDay else DayType.BusinessDay

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the base calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return frozenset((self.base_calendar.calendar_id,))


def range_start_days(calendar: BDCalendar) -> RangeStartDaysBDCalendar:
    """Create a contiguous-business-range start selector.

    :param calendar: Calendar whose ranges are inspected.
    :returns: Range-start calendar.
    """
    return RangeStartDaysBDCalendar(calendar)

