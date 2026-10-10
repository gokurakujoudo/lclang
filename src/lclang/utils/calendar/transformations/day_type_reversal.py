"""Day-type reversal calendar.

Defines ``RevertBDCalendar``.
"""

from collections.abc import Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar
from lclang.utils.calendar.transformations.calendar_dependency import dependency_day_type


@guard_constructor(LclValidationError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
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

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
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

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the reversed calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return frozenset((self.base_calendar.calendar_id,))

    @guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    def revert(self) -> BDCalendar:
        """Cancel a second reversal.

        :returns: Original base calendar.
        """
        return self.base_calendar
