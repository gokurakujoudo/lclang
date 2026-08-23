"""Calendar view of mapped source business dates."""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.utils.calendar.errors import DateOperationOutOfScopeException
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.helpers import safe_add_days
from lclang.utils.calendar.mapping.mapping import BDCalendarMapping
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.types import CalendarID, DayType


@final
class CalendarMapBDCalendar(FunctionalBDCalendar):
    """Classify targets reached by source business dates.

    :param calendar_id: Unique result calendar identifier.
    :param mapping: Applied source mapping.
    """

    __slots__ = ("mapping",)

    def __init__(self, calendar_id: CalendarID, mapping: BDCalendarMapping) -> None:
        """Create a calendar view over an applied mapping.

        :param calendar_id: Unique result calendar identifier.
        :param mapping: Applied source mapping.
        :returns: ``None``.
        :raises ValueError: If *mapping* is not applied.
        """
        if not mapping.has_applied:
            raise ValueError("calendar-map result requires an applied mapping")
        self.mapping = mapping
        super().__init__(calendar_id)

    async def get_day_type(self, d: date) -> DayType:
        """Return business when a source business date maps to *d*.

        :param d: Target date to classify.
        :returns: Business day when reached, otherwise holiday.
        """
        try:
            first, last = await self.mapping.map_date_reverse(d)
        except DateOperationOutOfScopeException:
            return DayType.Holiday
        current: date | None = first
        while current is not None and current <= last:
            if (
                await dependency_day_type(self.mapping.base_calendar, current)
                is DayType.BusinessDay
            ):
                return DayType.BusinessDay
            current = safe_add_days(current, 1)
        return DayType.Holiday

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return all direct mapping dependencies.

        :returns: Immutable dependency set.
        """
        return await self.mapping.get_dependency_ids()
