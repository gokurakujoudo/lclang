"""Business-day intersection calendar.

Defines ``IntersectBDCalendar``.
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
from lclang.utils.calendar.transformations.calendar_operand import canonical_calendars


@guard_constructor(LclValidationError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
@final
class IntersectBDCalendar(FunctionalBDCalendar):
    """Combine defined calendars with holiday veto semantics.

    :param base_calendars: Calendars to combine as a commutative set.
    """

    __slots__ = ("base_calendars",)

    def __init__(self, base_calendars: Iterable[BDCalendar]) -> None:
        """Create a canonical flattened intersection.

        :param base_calendars: Calendars to combine as a commutative set.
        :returns: ``None``.
        """
        bases = canonical_calendars(base_calendars)
        self.base_calendars = frozenset(bases)
        super().__init__(CalendarID(f"({' & '.join(map(repr, bases))})"))

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Apply undefined-aware holiday-veto intersection semantics.

        :param d: Date to classify.
        :returns: Intersection classification.
        """
        values = [
            await dependency_day_type(calendar, d) for calendar in self.base_intersect_calendars()
        ]
        if all(value is DayType.Undefined for value in values):
            return DayType.Undefined
        if DayType.Holiday in values:
            return DayType.Holiday
        return DayType.BusinessDay

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct intersection operand IDs.

        :returns: Immutable direct dependency set.
        """
        return frozenset(calendar.calendar_id for calendar in self.base_calendars)

    @guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
    def base_intersect_calendars(self) -> tuple[BDCalendar, ...]:
        """Return canonical flattened intersection operands.

        :returns: Stable operand tuple.
        """
        return tuple(sorted(self.base_calendars, key=lambda item: item.calendar_id))
