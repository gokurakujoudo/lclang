"""Signed business-day shift mapping operation."""

from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.constants import MAX_BUSINESS_DAY_SHIFT_DAYS
from lclang.utils.calendar.helpers import dependency_date
from lclang.utils.calendar.mapping.base import BDCalendarMapOperation
from lclang.utils.calendar.mapping.sentinel import SELF_CALENDAR


@final
class ShiftNDaysMapOperation(BDCalendarMapOperation):
    """Shift dates by a signed number of strict business days.

    :param n: Signed business-day count.
    :param base_calendar: Calendar used for traversal.
    :raises TypeError: If *n* is not an integer.
    :raises ValueError: If the count exceeds the primitive operation bound.
    """

    __slots__ = ("n",)

    def __init__(self, n: int, base_calendar: BDCalendar = SELF_CALENDAR) -> None:
        """Create a bounded signed shift.

        :param n: Signed business-day count.
        :param base_calendar: Calendar used for traversal.
        :returns: ``None``.
        :raises TypeError: If *n* is not an integer.
        :raises ValueError: If the count exceeds the primitive operation bound.
        """
        if not isinstance(n, int) or isinstance(n, bool):
            raise TypeError("business-day shift must be an integer")
        if abs(n) > MAX_BUSINESS_DAY_SHIFT_DAYS:
            raise ValueError("business-day shift exceeds primitive mapping bound")
        self.n = n
        super().__init__(base_calendar)

    async def map_date(self, base_date: date) -> date:
        """Shift one date by the configured business-day count.

        :param base_date: Source date.
        :returns: Shifted target date.
        """
        cached = self._mapped_dates.get(base_date)
        if cached is not None:
            return cached
        target = base_date
        if self.n == 0:
            target = await dependency_date(
                self.base_calendar,
                self.base_calendar.this_or_next_bd(target),
            )
        elif self.n > 0:
            for _ in range(self.n):
                target = await dependency_date(
                    self.base_calendar,
                    self.base_calendar.next_bd(target),
                )
        else:
            for _ in range(-self.n):
                target = await dependency_date(
                    self.base_calendar,
                    self.base_calendar.prev_bd(target),
                )
        return self.validate_displacement(base_date, target)

    def with_base_calendar(self, calendar: BDCalendar) -> ShiftNDaysMapOperation:
        """Return a new operation bound to a calendar.

        :param calendar: Concrete mapping calendar.
        :returns: New bound operation.
        """
        return ShiftNDaysMapOperation(self.n, calendar)

    def __repr__(self) -> str:
        """Return the chain-call representation.

        :returns: Stable operation representation.
        """
        return f".shift_n_days({self.n}, {self.base_calendar!r})"
