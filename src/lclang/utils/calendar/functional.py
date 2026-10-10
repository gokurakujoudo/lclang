"""Per-date functional calendar strategy."""

from abc import abstractmethod
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from lclang.error import LclError, LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor
from lclang.error.calendar import (
    CalendarLogicException,
    DateOperationOutOfScopeException,
    wrap_calendar_failure,
)
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.constants import MAX_BUSINESS_DAY_GAP_DAYS
from lclang.utils.calendar.helpers import (
    CALENDAR_ERRORS,
    require_day_type,
    safe_add_days,
    year_dates,
)
from lclang.utils.calendar.types import CalendarID, DayType


@guard_constructor(LclValidationError, utilities_codes.NATIVE_711)
class FunctionalBDCalendar(BDCalendar):
    """Implement traversal around an abstract per-date classifier.

    :param calendar_id: Unique calendar identifier.
    """

    __slots__ = ("_defined_dates", "defined_dates")

    def __init__(self, calendar_id: CalendarID) -> None:
        """Create an empty classification cache.

        :param calendar_id: Unique calendar identifier.
        :returns: ``None``.
        """
        super().__init__(calendar_id)
        self._defined_dates: dict[date, DayType] = {}
        self.defined_dates: Mapping[date, DayType] = MappingProxyType(self._defined_dates)

    @abstractmethod
    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_711)
    async def get_day_type(self, d: date) -> DayType:
        """Calculate one date's classification.

        :param d: Date to classify.
        :returns: Calculated day type.
        """

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_711)
    async def cached_day_type(self, d: date) -> DayType:
        """Return and cache one validated classifier result.

        :param d: Date to classify.
        :returns: Cached or newly calculated day type.
        :raises CalendarLogicException: If classifier logic fails unexpectedly.
        """
        cached = self._defined_dates.get(d)
        if cached is not None:
            return cached
        try:
            value = require_day_type(await self.get_day_type(d))
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
                        else utilities_codes.E11_SELF_CALENDAR_ID
                    ),
                ),
            )
            raise failure from failure.__cause__
        self._defined_dates[d] = value
        return value

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_711)
    async def next_bd(self, d: date) -> date:
        """Search forward within the configured gap bound.

        :param d: Source date.
        :returns: Next business date.
        :raises DateOperationOutOfScopeException: If the search is exhausted.
        """
        for offset in range(1, MAX_BUSINESS_DAY_GAP_DAYS + 1):
            candidate = safe_add_days(d, offset)
            if candidate is None:
                break
            if await self.cached_day_type(candidate) is DayType.BusinessDay:
                return candidate
        raise DateOperationOutOfScopeException(d, self, code=utilities_codes.E11_D)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_711)
    async def prev_bd(self, d: date) -> date:
        """Search backward within the configured gap bound.

        :param d: Source date.
        :returns: Previous business date.
        :raises DateOperationOutOfScopeException: If the search is exhausted.
        """
        for offset in range(1, MAX_BUSINESS_DAY_GAP_DAYS + 1):
            candidate = safe_add_days(d, -offset)
            if candidate is None:
                break
            if await self.cached_day_type(candidate) is DayType.BusinessDay:
                return candidate
        raise DateOperationOutOfScopeException(d, self, code=utilities_codes.E11_D)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_711)
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Calculate and cache every date in one year.

        :param year: Gregorian year from 1 through 9999.
        :returns: Complete date-to-day-type mapping.
        :raises LclValidationError: If *year* is outside the supported range.
        """
        return {d: await self.cached_day_type(d) for d in year_dates(year)}
