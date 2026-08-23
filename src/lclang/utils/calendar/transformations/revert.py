"""Day-type reversal calendar."""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.types import CalendarID, DayType


@final
class RevertBDCalendar(FunctionalBDCalendar):
    """Exchange business and holiday values while preserving undefined.

    :param base_calendar: Calendar whose day types are reversed.
    """

    __slots__ = ("base_calendar",)

    def __init__(self, base_calendar: BDCalendar) -> None:
        """Create a reversed calendar.

        :param base_calendar: Calendar whose day types are reversed.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        super().__init__(CalendarID(f"~{base_calendar!r}"))

    async def get_day_type(self, d: date) -> DayType:
        """Reverse one dependency classification.

        :param d: Date to classify.
        :returns: Reversed day type.
        """
        value = await dependency_day_type(self.base_calendar, d)
        if value is DayType.BusinessDay:
            return DayType.Holiday
        if value is DayType.Holiday:
            return DayType.BusinessDay
        return DayType.Undefined

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the reversed calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return frozenset((self.base_calendar.calendar_id,))

    def revert(self) -> BDCalendar:
        """Cancel a second reversal.

        :returns: Original base calendar.
        """
        return self.base_calendar

