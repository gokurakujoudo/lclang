"""Business day adjustment.

Defines ``adjust_business_day``, ``ThisOrNextMapOperation``, ``ThisOrPrevMapOperation``.
"""

from __future__ import annotations

from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.operation_guard import guard_async_failure, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_date_operation import dependency_date
from lclang.utils.calendar.mapping.date_map_operation import BDCalendarMapOperation


@guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
async def adjust_business_day(
    operation: BDCalendarMapOperation,
    base_date: date,
    *,
    forward: bool,
) -> date:
    """Reuse successful mappings before adjusting through the selected calendar.

    :param operation: Mapping operation owning the result cache.
    :param base_date: Source date to adjust.
    :param forward: Select this-or-next when true, otherwise this-or-previous.
    :returns: Validated, cached target date.
    :raises DateOperationOutOfScopeException: If the displacement exceeds its limit.
    :raises CalendarLogicException: If dependency adjustment fails unexpectedly.
    """
    cached = operation.mapped_dates.get(base_date)
    if cached is not None:
        return cached
    calendar = operation.base_calendar
    adjust = calendar.this_or_next_bd if forward else calendar.this_or_prev_bd
    target = await dependency_date(calendar, adjust(base_date))
    return operation.validate_displacement(base_date, target)


@final
class ThisOrNextMapOperation(BDCalendarMapOperation):
    """Map a date to this-or-next business day.

    :param base_calendar: Calendar used for adjustment.
    """

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def map_date(self, base_date: date) -> date:
        """Map through this-or-next business-day lookup.

        :param base_date: Source date.
        :returns: Adjusted target date.
        """
        return await adjust_business_day(self, base_date, forward=True)

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def with_base_calendar(self, calendar: BDCalendar) -> ThisOrNextMapOperation:
        """Return a new operation bound to a calendar.

        :param calendar: Concrete mapping calendar.
        :returns: New bound operation.
        """
        return ThisOrNextMapOperation(calendar)

    def __repr__(self) -> str:
        """Return the chain-call representation.

        :returns: Stable operation representation.
        """
        return f".map_this_or_next({self.base_calendar!r})"


@final
class ThisOrPrevMapOperation(BDCalendarMapOperation):
    """Map a date to this-or-previous business day.

    :param base_calendar: Calendar used for adjustment.
    """

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def map_date(self, base_date: date) -> date:
        """Map through this-or-previous business-day lookup.

        :param base_date: Source date.
        :returns: Adjusted target date.
        """
        return await adjust_business_day(self, base_date, forward=False)

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def with_base_calendar(self, calendar: BDCalendar) -> ThisOrPrevMapOperation:
        """Return a new operation bound to a calendar.

        :param calendar: Concrete mapping calendar.
        :returns: New bound operation.
        """
        return ThisOrPrevMapOperation(calendar)

    def __repr__(self) -> str:
        """Return the chain-call representation.

        :returns: Stable operation representation.
        """
        return f".map_this_or_prev({self.base_calendar!r})"
