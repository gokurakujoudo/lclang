"""Ordered undefined-date fallback calendar.

Defines ``FallbackBDCalendar``.
"""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar
from lclang.utils.calendar.transformations.calendar_dependency import dependency_day_type
from lclang.utils.calendar.transformations.calendar_operand import ordered_calendars


@guard_constructor(LclValidationError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
@final
class FallbackBDCalendar(FunctionalBDCalendar):
    """Use the first calendar that defines a date.

    :param base_calendars: Calendars in descending priority order.
    """

    __slots__ = ("base_calendars",)

    def __init__(self, base_calendars: Iterable[BDCalendar]) -> None:
        """Create an ordered flattened fallback.

        :param base_calendars: Calendars in descending priority order.
        :returns: ``None``.
        """
        bases = ordered_calendars(base_calendars)
        self.base_calendars = bases
        super().__init__(CalendarID(f"({' >> '.join(map(repr, bases))})"))

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Return the first defined classification.

        :param d: Date to classify.
        :returns: First defined day type or undefined.
        """
        for calendar in self.base_calendars:
            value = await dependency_day_type(calendar, d)
            if value is not DayType.Undefined:
                return value
        return DayType.Undefined

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct fallback operand IDs.

        :returns: Immutable direct dependency set.
        """
        return frozenset(calendar.calendar_id for calendar in self.base_calendars)

    @guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    def base_fallback_calendars(self) -> tuple[BDCalendar, ...]:
        """Return flattened ordered fallback operands.

        :returns: Ordered operand tuple.
        """
        return self.base_calendars
