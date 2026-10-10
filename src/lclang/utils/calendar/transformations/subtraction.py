"""Business-day subtraction calendar."""

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
from lclang.utils.calendar.transformations.operands import canonical_calendars
from lclang.utils.calendar.types import CalendarID, DayType


@guard_constructor(LclValidationError, utilities_codes.NATIVE_714)
@final
class SubtractionBDCalendar(FunctionalBDCalendar):
    """Turn base business days into holidays when subtrahends accept them.

    :param base_calendar: Calendar whose defined classifications are retained.
    :param to_subtract: Calendars whose business days are removed.
    """

    __slots__ = ("base_calendar", "to_subtract")

    def __init__(self, base_calendar: BDCalendar, to_subtract: Iterable[BDCalendar]) -> None:
        """Create a canonical subtraction calendar.

        :param base_calendar: Calendar whose classifications are retained.
        :param to_subtract: Calendars whose business days are removed.
        :returns: ``None``.
        :raises LclValidationError: If *base_calendar* is not a calendar.
        """
        if not isinstance(base_calendar, BDCalendar):
            raise LclValidationError(
                "base calendar must be a BDCalendar",
                code=utilities_codes.E14_BASE_CALENDAR_MUST_BE_A_BDCALENDAR,
            )
        values = canonical_calendars(to_subtract)
        self.base_calendar = base_calendar
        self.to_subtract = frozenset(values)
        suffix = " - ".join(map(repr, values))
        super().__init__(CalendarID(f"({base_calendar!r} - {suffix})"))

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
    async def get_day_type(self, d: date) -> DayType:
        """Apply subtraction truth-table semantics.

        :param d: Date to classify.
        :returns: Subtracted classification.
        """
        base = await dependency_day_type(self.base_calendar, d)
        if base is DayType.Undefined:
            return DayType.Undefined
        if base is DayType.Holiday:
            return DayType.Holiday
        for calendar in sorted(self.to_subtract, key=lambda item: item.calendar_id):
            if await dependency_day_type(calendar, d) is DayType.BusinessDay:
                return DayType.Holiday
        return DayType.BusinessDay

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return base and subtrahend IDs.

        :returns: Immutable direct dependency set.
        """
        return frozenset(
            (self.base_calendar.calendar_id, *(item.calendar_id for item in self.to_subtract))
        )

    @guard_failure(LclUtilityError, utilities_codes.NATIVE_714)
    def minus(self, another: BDCalendar) -> SubtractionBDCalendar:
        """Append another canonical subtrahend.

        :param another: Additional calendar to subtract.
        :returns: New flattened subtraction calendar.
        """
        return SubtractionBDCalendar(self.base_calendar, (*self.to_subtract, another))
