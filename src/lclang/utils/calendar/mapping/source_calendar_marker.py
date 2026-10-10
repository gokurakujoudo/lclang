"""Unapplied source-calendar sentinel.

Defines ``SelfCalendar``.
"""

from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import UnappliedCalendarOperationException
from lclang.error.operation_guard import guard_async_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID, DayType


@final
class SelfCalendar(BDCalendar):
    """Represent a source calendar that has not yet been applied."""

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Reject direct sentinel classification.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(
            code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
        )

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def next_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(
            code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
        )

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def prev_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(
            code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
        )

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Reject direct sentinel generation.

        :param year: Unused source year.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(
            code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
        )


# Singleton placeholder for an operation's eventual source calendar.
# Unitless singleton identity marks an unapplied mapping, following the calendar mapping
# contract. A distinct SELF_CALENDAR object postpones binding without confusing a real input
# calendar with an omitted one.
SELF_CALENDAR = SelfCalendar(CalendarID("SELF_CALENDAR"))
