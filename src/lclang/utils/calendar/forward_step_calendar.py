"""Forward-generated sparse business-day calendar strategy.

Defines ``ForwardStepBDCalendar``.
"""

from abc import abstractmethod
from bisect import bisect_left
from collections.abc import Sequence
from datetime import date

from lclang.error import LclError, LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import (
    CalendarLogicException,
    DateOperationOutOfScopeException,
    wrap_calendar_failure,
)
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_date_operation import CALENDAR_ERRORS, safe_add_days, year_dates
from lclang.utils.calendar.calendar_type import CalendarID, DayType


@guard_constructor(LclValidationError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE)
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
        :raises LclValidationError: If *first_bd* is not a date.
        """
        super().__init__(calendar_id)
        if not isinstance(first_bd, date):
            raise LclValidationError(
                "first business day must be a date",
                code=UtilityErrorCode.E17_FIRST_BUSINESS_DAY_MUST_BE_A_DATE,
            )
        self.first_bd = first_bd
        self._defined_business_days = [first_bd]
        self._fully_cached = False

    @property
    @guard_failure(LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE)
    def defined_business_days(self) -> Sequence[date]:
        """Return an immutable snapshot of discovered business dates.

        :returns: Ordered discovered dates.
        """
        return tuple(self._defined_business_days)

    @property
    @guard_failure(LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE)
    def fully_cached(self) -> bool:
        """Return whether the generator has reported exhaustion.

        :returns: Exhaustion flag.
        """
        return self._fully_cached

    @abstractmethod
    @guard_async_failure(
        LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE
    )
    async def next_bd(self, d: date) -> date:
        """Calculate the next generated business day.

        :param d: Previously generated business day.
        :returns: Next generated business day.
        :raises DateOperationOutOfScopeException: If the sequence is exhausted.
        """

    @guard_async_failure(
        LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE
    )
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
                failure = wrap_calendar_failure(
                    error,
                    CalendarLogicException(
                        self.calendar_id,
                        code=(
                            error.code
                            if isinstance(error, LclError)
                            else UtilityErrorCode.E17_DATE_GENERATOR_FAILURE
                        ),
                    ),
                )
                raise failure from failure.__cause__
            if not isinstance(following, date) or following <= previous:
                generated_error = LclValidationError(
                    "forward business dates must increase",
                    code=UtilityErrorCode.E17_FORWARD_BUSINESS_DATES_MUST_INCREASE,
                )
                failure = wrap_calendar_failure(
                    generated_error,
                    CalendarLogicException(
                        self.calendar_id, code=UtilityErrorCode.E17_DATE_GENERATOR_FAILURE
                    ),
                )
                raise failure from failure.__cause__
            self._defined_business_days.append(following)

    @guard_async_failure(
        LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE
    )
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

    @guard_async_failure(
        LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE
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
            raise DateOperationOutOfScopeException(
                d, self, code=UtilityErrorCode.E17_DATE_OUT_OF_SCOPE
            )
        return self._defined_business_days[index]

    @guard_async_failure(
        LclUtilityError, UtilityErrorCode.E17_CALENDAR_DATE_GENERATION_NATIVE_FAILURE
    )
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Return generated business dates in one year.

        :param year: Gregorian year from 1 through 9999.
        :returns: Sparse business-day mapping.
        :raises LclValidationError: If *year* is outside the supported range.
        """
        dates = year_dates(year)
        next(dates, None)
        end = date(year, 12, 31)
        if end >= self.first_bd:
            after = safe_add_days(end, 1)
            await self.cache_through(end if after is None else after)
        return {d: DayType.BusinessDay for d in self._defined_business_days if d.year == year}
