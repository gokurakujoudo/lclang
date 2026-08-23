"""This-or-next business-day mapping operation."""

from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.helpers import dependency_date
from lclang.utils.calendar.mapping.base import BDCalendarMapOperation


@final
class ThisOrNextMapOperation(BDCalendarMapOperation):
    """Map a date to this-or-next business day.

    :param base_calendar: Calendar used for adjustment.
    """

    async def map_date(self, base_date: date) -> date:
        """Map through this-or-next business-day lookup.

        :param base_date: Source date.
        :returns: Adjusted target date.
        """
        cached = self._mapped_dates.get(base_date)
        if cached is not None:
            return cached
        target = await dependency_date(
            self.base_calendar,
            self.base_calendar.this_or_next_bd(base_date),
        )
        return self.validate_displacement(base_date, target)

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
