"""Calendar view of mapped source business dates.

Defines ``CalendarMapBDCalendar``.
"""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import DateOperationOutOfScopeException
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor
from lclang.utils.calendar.calendar_date_operation import safe_add_days
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar
from lclang.utils.calendar.mapping.calendar_mapping import BDCalendarMapping
from lclang.utils.calendar.transformations.calendar_dependency import dependency_day_type


@guard_constructor(LclValidationError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
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
        :raises LclValidationError: If *mapping* is not applied.
        """
        if not mapping.has_applied:
            raise LclValidationError(
                "calendar-map result requires an applied mapping",
                code=UtilityErrorCode.E13_CALENDAR_MAP_RESULT_REQUIRES_AN_APPLIED_MAPPING,
            )
        self.mapping = mapping
        super().__init__(calendar_id)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
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

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return all direct mapping dependencies.

        :returns: Immutable dependency set.
        """
        return await self.mapping.get_dependency_ids()
