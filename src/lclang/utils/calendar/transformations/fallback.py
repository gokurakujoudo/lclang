"""Ordered undefined-date fallback calendar."""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.transformations.operands import ordered_calendars
from lclang.utils.calendar.types import CalendarID, DayType


@guard_constructor(LclValidationError, utilities_codes.NATIVE_714)
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

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
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

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct fallback operand IDs.

        :returns: Immutable direct dependency set.
        """
        return frozenset(calendar.calendar_id for calendar in self.base_calendars)

    @guard_failure(LclUtilityError, utilities_codes.NATIVE_714)
    def base_fallback_calendars(self) -> tuple[BDCalendar, ...]:
        """Return flattened ordered fallback operands.

        :returns: Ordered operand tuple.
        """
        return self.base_calendars
