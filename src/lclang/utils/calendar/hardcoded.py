"""Static date-to-day-type calendar implementation."""

from bisect import bisect_left, bisect_right
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import DateOperationOutOfScopeException
from lclang.utils.calendar.helpers import year_dates
from lclang.utils.calendar.types import CalendarID, DayType


class HardcodedBDCalendar(BDCalendar):
    """Classify dates from one immutable explicit mapping.

    :param calendar_id: Unique calendar identifier.
    :param defined_dates: Explicit date classifications to snapshot.
    :raises TypeError: If a key or value has an incompatible type.
    """

    __slots__ = ("_business_days", "_defined_dates", "defined_dates")

    def __init__(
        self,
        calendar_id: CalendarID,
        defined_dates: Mapping[date, DayType],
    ) -> None:
        """Create a detached static calendar.

        :param calendar_id: Unique calendar identifier.
        :param defined_dates: Explicit date classifications to snapshot.
        :returns: ``None``.
        :raises TypeError: If a key or value has an incompatible type.
        """
        super().__init__(calendar_id)
        if any(not isinstance(d, date) for d in defined_dates):
            raise TypeError("hardcoded calendar keys must be dates")
        if any(not isinstance(value, DayType) for value in defined_dates.values()):
            raise TypeError("hardcoded calendar values must be DayType")
        snapshot = {
            d: value for d, value in defined_dates.items() if value is not DayType.Undefined
        }
        self._defined_dates = snapshot
        self.defined_dates = MappingProxyType(snapshot)
        self._business_days = tuple(
            sorted(d for d, value in snapshot.items() if value is DayType.BusinessDay)
        )

    async def get_day_type(self, d: date) -> DayType:
        """Return an explicit classification or ``Undefined``.

        :param d: Date to classify.
        :returns: Stored day type or :attr:`DayType.Undefined`.
        """
        return self._defined_dates.get(d, DayType.Undefined)

    async def next_bd(self, d: date) -> date:
        """Return the next stored business day.

        :param d: Source date.
        :returns: Next explicit business date.
        :raises DateOperationOutOfScopeException: If no later business date exists.
        """
        index = bisect_right(self._business_days, d)
        if index == len(self._business_days):
            raise DateOperationOutOfScopeException(d, self)
        return self._business_days[index]

    async def prev_bd(self, d: date) -> date:
        """Return the previous stored business day.

        :param d: Source date.
        :returns: Previous explicit business date.
        :raises DateOperationOutOfScopeException: If no earlier business date exists.
        """
        index = bisect_left(self._business_days, d) - 1
        if index < 0:
            raise DateOperationOutOfScopeException(d, self)
        return self._business_days[index]

    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Return explicit classifications in one year.

        :param year: Gregorian year from 1 through 9999.
        :returns: Detached mapping containing explicit classifications.
        :raises ValueError: If *year* is outside the supported range.
        """
        next(year_dates(year), None)
        return {d: value for d, value in self._defined_dates.items() if d.year == year}
