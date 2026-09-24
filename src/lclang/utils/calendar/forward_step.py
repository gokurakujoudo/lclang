"""Forward-generated sparse business-day calendar strategy."""

from abc import abstractmethod
from bisect import bisect_left
from collections.abc import Sequence
from datetime import date

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import CalendarLogicException, DateOperationOutOfScopeException
from lclang.utils.calendar.helpers import CALENDAR_ERRORS, safe_add_days, year_dates
from lclang.utils.calendar.types import CalendarID, DayType


class ForwardStepBDCalendar(BDCalendar):
    """Discover ordered business dates from a first date and forward step.

    :param calendar_id: Unique calendar identifier.
    :param first_bd: First business day in the generated sequence.
    """

    __slots__ = ("_defined_business_days", "_fully_cached", "first_bd")

    def __init__(self, calendar_id: CalendarID, first_bd: date) -> None:
        """Create a forward cache containing its first business day.

        :param calendar_id: Unique calendar identifier.
        :param first_bd: First business day in the generated sequence.
        :returns: ``None``.
        :raises TypeError: If *first_bd* is not a date.
        """
        super().__init__(calendar_id)
        if not isinstance(first_bd, date):
            raise TypeError("first business day must be a date")
        self.first_bd = first_bd
        self._defined_business_days = [first_bd]
        self._fully_cached = False

    @property
    def defined_business_days(self) -> Sequence[date]:
        """Return an immutable snapshot of discovered business dates.

        :returns: Ordered discovered dates.
        """
        return tuple(self._defined_business_days)

    @property
    def fully_cached(self) -> bool:
        """Return whether the generator has reported exhaustion.

        :returns: Exhaustion flag.
        """
        return self._fully_cached

    @abstractmethod
    async def next_bd(self, d: date) -> date:
        """Calculate the next generated business day.

        :param d: Previously generated business day.
        :returns: Next generated business day.
        :raises DateOperationOutOfScopeException: If the sequence is exhausted.
        """

    async def cache_through(self, d: date) -> None:
        """Extend the ordered cache until it reaches or passes a date.

        :param d: Date the cache must reach or pass.
        :returns: ``None``.
        :raises CalendarLogicException: If generated dates are not increasing.
        """
        while not self._fully_cached and self._defined_business_days[-1] < d:
            previous = self._defined_business_days[-1]
            try:
                following = await self.next_bd(previous)
            except DateOperationOutOfScopeException:
                self._fully_cached = True
                return
            except CALENDAR_ERRORS:
                raise
            except Exception as error:
                raise CalendarLogicException(self.calendar_id) from error
            if not isinstance(following, date) or following <= previous:
                generated_error = ValueError("forward business dates must increase")
                raise CalendarLogicException(self.calendar_id) from generated_error
            self._defined_business_days.append(following)

    async def get_day_type(self, d: date) -> DayType:
        """Return business for discovered dates and undefined otherwise.

        :param d: Date to classify.
        :returns: Business day or undefined.
        """
        if d >= self.first_bd:
            await self.cache_through(d)
        index = bisect_left(self._defined_business_days, d)
        return (
            DayType.BusinessDay
            if index < len(self._defined_business_days) and self._defined_business_days[index] == d
            else DayType.Undefined
        )

    async def prev_bd(self, d: date) -> date:
        """Return the previous generated business date.

        :param d: Source date.
        :returns: Previous discovered business date.
        :raises DateOperationOutOfScopeException: If no earlier generated date exists.
        """
        await self.cache_through(d)
        index = bisect_left(self._defined_business_days, d) - 1
        if index < 0:
            raise DateOperationOutOfScopeException(d, self)
        return self._defined_business_days[index]

    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Return generated business dates in one year.

        :param year: Gregorian year from 1 through 9999.
        :returns: Sparse business-day mapping.
        :raises ValueError: If *year* is outside the supported range.
        """
        dates = year_dates(year)
        next(dates, None)
        end = date(year, 12, 31)
        if end >= self.first_bd:
            after = safe_add_days(end, 1)
            await self.cache_through(end if after is None else after)
        return {d: DayType.BusinessDay for d in self._defined_business_days if d.year == year}
