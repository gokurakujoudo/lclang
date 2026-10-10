"""Range boundaries."""

from __future__ import annotations

from collections.abc import Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.helpers import safe_add_days
from lclang.utils.calendar.transformations.logic import dependency_day_type, direct_dependency_ids
from lclang.utils.calendar.types import CalendarID, DayType


@guard_async_failure(LclUtilityError, utilities_codes.NATIVE_715)
async def classify_range_boundary(calendar: BDCalendar, d: date, direction: int) -> DayType:
    """Select business dates adjacent to a non-business day or date boundary.

    :param calendar: Calendar whose contiguous ranges are inspected.
    :param d: Candidate date.
    :param direction: Adjacent offset in days: -1 for starts, +1 for ends.
    :returns: Business for a range boundary, otherwise holiday.
    :raises CalendarLogicException: If dependency classification fails unexpectedly.
    """
    if await dependency_day_type(calendar, d) is not DayType.BusinessDay:
        return DayType.Holiday
    adjacent = safe_add_days(d, direction)
    if adjacent is None:
        return DayType.BusinessDay
    value = await dependency_day_type(calendar, adjacent)
    return DayType.Holiday if value is DayType.BusinessDay else DayType.BusinessDay


@guard_constructor(LclValidationError, utilities_codes.NATIVE_715)
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

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_715)
    async def get_day_type(self, d: date) -> DayType:
        """Classify first dates of business ranges.

        :param d: Date to classify.
        :returns: Business on a range start, otherwise holiday.
        """
        return await classify_range_boundary(self.base_calendar, d, -1)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_715)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the base calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))


@guard_failure(LclUtilityError, utilities_codes.NATIVE_715)
def range_start_days(calendar: BDCalendar) -> RangeStartDaysBDCalendar:
    """Create a contiguous-business-range start selector.

    :param calendar: Calendar whose ranges are inspected.
    :returns: Range-start calendar.
    """
    return RangeStartDaysBDCalendar(calendar)


@guard_constructor(LclValidationError, utilities_codes.NATIVE_715)
@final
class RangeEndDaysBDCalendar(FunctionalBDCalendar):
    """Select last dates of contiguous base-calendar business ranges.

    :param base_calendar: Calendar whose ranges are inspected.
    """

    __slots__ = ("base_calendar",)

    def __init__(self, base_calendar: BDCalendar) -> None:
        """Create a range-end selector.

        :param base_calendar: Calendar whose ranges are inspected.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        super().__init__(CalendarID(f"range_end_days({base_calendar!r})"))

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_715)
    async def get_day_type(self, d: date) -> DayType:
        """Classify last dates of business ranges.

        :param d: Date to classify.
        :returns: Business on a range end, otherwise holiday.
        """
        return await classify_range_boundary(self.base_calendar, d, 1)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_715)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the base calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return await direct_dependency_ids((self.base_calendar,))


@guard_failure(LclUtilityError, utilities_codes.NATIVE_715)
def range_end_days(calendar: BDCalendar) -> RangeEndDaysBDCalendar:
    """Create a contiguous-business-range end selector.

    :param calendar: Calendar whose ranges are inspected.
    :returns: Range-end calendar.
    """
    return RangeEndDaysBDCalendar(calendar)
