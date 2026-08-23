"""Year-batch calendar strategy."""

from abc import abstractmethod
from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.constants import MAX_BUSINESS_DAY_GAP_DAYS
from lclang.utils.calendar.errors import CalendarLogicException, DateOperationOutOfScopeException
from lclang.utils.calendar.helpers import (
    CALENDAR_ERRORS,
    require_day_type,
    safe_add_days,
    year_dates,
)
from lclang.utils.calendar.types import CalendarID, DayType


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
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Load one year from the concrete source.

        :param year: Gregorian year from 1 through 9999.
        :returns: Date-to-day-type mapping for the requested year.
        """

    async def loaded_year(self, year: int) -> Mapping[date, DayType]:
        """Return one validated cached year batch.

        :param year: Gregorian year from 1 through 9999.
        :returns: Detached normalized year mapping.
        :raises CalendarLogicException: If generation returns invalid content.
        :raises TypeError: If generated content has incompatible types.
        :raises ValueError: If generated dates are outside the requested year.
        """
        next(year_dates(year), None)
        cached = self._loaded_year_batches.get(year)
        if cached is not None:
            return cached
        try:
            raw = await self.gen_year(year)
            if not isinstance(raw, dict):
                raise TypeError("year generator must return a dictionary")
            normalized: dict[date, DayType] = {}
            for d, value in raw.items():
                if not isinstance(d, date) or d.year != year:
                    raise ValueError("year batch contains a date outside its year")
                selected = require_day_type(value)
                if selected is not DayType.Undefined:
                    normalized[d] = selected
        except CALENDAR_ERRORS:
            raise
        except Exception as error:
            raise CalendarLogicException(self.calendar_id) from error
        published: Mapping[date, DayType] = MappingProxyType(normalized)
        self._loaded_year_batches[year] = published
        return published

    async def get_day_type(self, d: date) -> DayType:
        """Return a date from its cached year batch.

        :param d: Date to classify.
        :returns: Loaded classification or ``Undefined``.
        """
        return (await self.loaded_year(d.year)).get(d, DayType.Undefined)

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
        raise DateOperationOutOfScopeException(d, self)

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
        raise DateOperationOutOfScopeException(d, self)
