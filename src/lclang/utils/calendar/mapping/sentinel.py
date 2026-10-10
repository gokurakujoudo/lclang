"""Unapplied source-calendar sentinel."""

from datetime import date
from typing import final

from lclang.error import LclUtilityError
from lclang.error.boundary import guard_async_failure
from lclang.error.calendar import UnappliedCalendarOperationException
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


@final
class SelfCalendar(BDCalendar):
    """Represent a source calendar that has not yet been applied."""

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_713)
    async def get_day_type(self, d: date) -> DayType:
        """Reject direct sentinel classification.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(code=utilities_codes.E13_OPERATION_IS_UNAVAILABLE)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_713)
    async def next_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(code=utilities_codes.E13_OPERATION_IS_UNAVAILABLE)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_713)
    async def prev_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(code=utilities_codes.E13_OPERATION_IS_UNAVAILABLE)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_713)
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Reject direct sentinel generation.

        :param year: Unused source year.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException(code=utilities_codes.E13_OPERATION_IS_UNAVAILABLE)


# Singleton placeholder for an operation's eventual source calendar.
# Unitless singleton identity marks an unapplied mapping, following the calendar mapping
# contract. A distinct SELF_CALENDAR object postpones binding without confusing a real input
# calendar with an omitted one.
SELF_CALENDAR = SelfCalendar(CalendarID("SELF_CALENDAR"))
