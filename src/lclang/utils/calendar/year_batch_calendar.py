"""Year-batch calendar strategy.

Defines ``YearBatchBDCalendar``.
"""

from abc import abstractmethod
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from lclang.error import LclError, LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import (
    CalendarLogicException,
    DateOperationOutOfScopeException,
    wrap_calendar_failure,
)
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_date_operation import (
    CALENDAR_ERRORS,
    require_day_type,
    safe_add_days,
    year_dates,
)
from lclang.utils.calendar.calendar_limit import MAX_BUSINESS_DAY_GAP_DAYS
from lclang.utils.calendar.calendar_type import CalendarID, DayType


@guard_constructor(LclValidationError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
class YearBatchBDCalendar(BDCalendar):
    """Implement date lookup around abstract whole-year generation.

    :param calendar_id: Unique calendar identifier.
    """

    __slots__ = ("_loaded_year_batches", "loaded_year_batches")

    def __init__(self, calendar_id: CalendarID) -> None:
        """Create an empty year-batch cache.

        :param calendar_id: Unique calendar identifier.
        :returns: ``None``.
        """
        super().__init__(calendar_id)
        self._loaded_year_batches: dict[int, Mapping[date, DayType]] = {}
        self.loaded_year_batches: Mapping[int, Mapping[date, DayType]] = MappingProxyType(
            self._loaded_year_batches
        )

    @abstractmethod
    @guard_async_failure(LclUtilityError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Load one year from the concrete source.

        :param year: Gregorian year from 1 through 9999.
        :returns: Date-to-day-type mapping for the requested year.
        """

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
    async def loaded_year(self, year: int) -> Mapping[date, DayType]:
        """Return one validated cached year batch.

        :param year: Gregorian year from 1 through 9999.
        :returns: Detached normalized year mapping.
        :raises CalendarLogicException: If generation returns invalid content.
        :raises LclValidationError: If generated content has incompatible types.
        :raises LclValidationError: If generated dates are outside the requested year.
        """
        next(year_dates(year), None)
        cached = self._loaded_year_batches.get(year)
        if cached is not None:
            return cached
        try:
            raw = await self.gen_year(year)
            if not isinstance(raw, dict):
                raise LclValidationError(
                    "year generator must return a dictionary",
                    code=UtilityErrorCode.E18_YEAR_GENERATOR_MUST_RETURN_A_DICTIONARY,
                )
            normalized: dict[date, DayType] = {}
            for d, value in raw.items():
                if not isinstance(d, date) or d.year != year:
                    raise LclValidationError(
                        "year batch contains a date outside its year",
                        code=UtilityErrorCode.E18_YEAR_BATCH_CONTAINS_A_DATE_OUTSIDE_ITS_YEAR,
                    )
                selected = require_day_type(value)
                if selected is not DayType.Undefined:
                    normalized[d] = selected
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
                        else UtilityErrorCode.E18_YEAR_GENERATOR_FAILURE
                    ),
                ),
            )
            raise failure from failure.__cause__
        published: Mapping[date, DayType] = MappingProxyType(normalized)
        self._loaded_year_batches[year] = published
        return published

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
    async def get_day_type(self, d: date) -> DayType:
        """Return a date from its cached year batch.

        :param d: Date to classify.
        :returns: Loaded classification or ``Undefined``.
        """
        return (await self.loaded_year(d.year)).get(d, DayType.Undefined)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
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
            if await self.get_day_type(candidate) is DayType.BusinessDay:
                return candidate
        raise DateOperationOutOfScopeException(d, self, code=UtilityErrorCode.E18_DATE_OUT_OF_SCOPE)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E18_CALENDAR_YEAR_BATCH_NATIVE_FAILURE)
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
            if await self.get_day_type(candidate) is DayType.BusinessDay:
                return candidate
        raise DateOperationOutOfScopeException(d, self, code=UtilityErrorCode.E18_DATE_OUT_OF_SCOPE)
