"""Unapplied source-calendar sentinel."""

from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import UnappliedCalendarOperationException
from lclang.utils.calendar.types import CalendarID, DayType


@final
class SelfCalendar(BDCalendar):
    """Represent a source calendar that has not yet been applied."""

    async def get_day_type(self, d: date) -> DayType:
        """Reject direct sentinel classification.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException()

    async def next_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException()

    async def prev_bd(self, d: date) -> date:
        """Reject direct sentinel traversal.

        :param d: Unused source date.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException()

    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Reject direct sentinel generation.

        :param year: Unused source year.
        :returns: Never returns.
        :raises UnappliedCalendarOperationException: Always.
        """
        raise UnappliedCalendarOperationException()


# Singleton placeholder for an operation's eventual source calendar.
SELF_CALENDAR = SelfCalendar(CalendarID("SELF_CALENDAR"))

