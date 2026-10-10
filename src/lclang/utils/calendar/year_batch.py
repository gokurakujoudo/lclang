"""Year-batch calendar strategy."""

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


@guard_constructor(LclValidationError, utilities_codes.NATIVE_718)
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
    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_718)
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Load one year from the concrete source.

        :param year: Gregorian year from 1 through 9999.
        :returns: Date-to-day-type mapping for the requested year.
        """

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_718)
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
                    code=utilities_codes.E18_YEAR_GENERATOR_MUST_RETURN_A_DICTIONARY,
                )
            normalized: dict[date, DayType] = {}
            for d, value in raw.items():
                if not isinstance(d, date) or d.year != year:
                    raise LclValidationError(
                        "year batch contains a date outside its year",
                        code=utilities_codes.E18_YEAR_BATCH_CONTAINS_A_DATE_OUTSIDE_ITS_YEAR,
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
                        else utilities_codes.E18_SELF_CALENDAR_ID
                    ),
                ),
            )
            raise failure from failure.__cause__
        published: Mapping[date, DayType] = MappingProxyType(normalized)
        self._loaded_year_batches[year] = published
        return published

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_718)
    async def get_day_type(self, d: date) -> DayType:
        """Return a date from its cached year batch.

        :param d: Date to classify.
        :returns: Loaded classification or ``Undefined``.
        """
        return (await self.loaded_year(d.year)).get(d, DayType.Undefined)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_718)
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
        raise DateOperationOutOfScopeException(d, self, code=utilities_codes.E18_D)

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_718)
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
        raise DateOperationOutOfScopeException(d, self, code=utilities_codes.E18_D)
