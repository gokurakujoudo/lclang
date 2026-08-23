"""Nth-business-day-of-month factory."""

from calendar import monthrange
from collections.abc import Mapping, Set
from datetime import date
from types import MappingProxyType
from typing import Self, final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.builtins.all_days import ALL_DAYS
from lclang.utils.calendar.factories.nth_day import (
    NthDayOfMonthBDCalendar,
    canonical_nth,
    nth_day_of_month,
)
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.types import CalendarID, DayType


@final
class NthBusinessDayOfMonthBDCalendar(FunctionalBDCalendar):
    """Select signed business-day positions from a base calendar.

    :param base_calendar: Calendar defining business dates.
    :param nth: Canonical signed business-day positions.
    """

    __slots__ = ("_selected_months", "base_calendar", "nth", "selected_months")

    def __init__(self, base_calendar: BDCalendar, nth: tuple[int, ...]) -> None:
        """Create an nth-business-day selector.

        :param base_calendar: Calendar defining business dates.
        :param nth: Canonical signed business-day positions.
        :returns: ``None``.
        """
        self.base_calendar = base_calendar
        self.nth = nth
        self._selected_months: dict[tuple[int, int], frozenset[date]] = {}
        self.selected_months: Mapping[tuple[int, int], frozenset[date]] = MappingProxyType(
            self._selected_months
        )
        suffix = ", ".join(map(str, nth))
        super().__init__(CalendarID(f"nth_business_day_of_month({base_calendar!r}, {suffix})"))

    async def selected_dates(self, year: int, month: int) -> frozenset[date]:
        """Return cached selected business dates for one month.

        :param year: Gregorian year.
        :param month: Month number.
        :returns: Selected month dates.
        """
        key = (year, month)
        cached = self._selected_months.get(key)
        if cached is not None:
            return cached
        business = []
        for day in range(1, monthrange(year, month)[1] + 1):
            candidate = date(year, month, day)
            if await dependency_day_type(self.base_calendar, candidate) is DayType.BusinessDay:
                business.append(candidate)
        indexes = tuple(value - 1 if value > 0 else value for value in self.nth)
        selected = frozenset(
            business[index] for index in indexes if -len(business) <= index < len(business)
        )
        self._selected_months[key] = selected
        return selected

    async def get_day_type(self, d: date) -> DayType:
        """Classify a date by its business-day month position.

        :param d: Date to classify.
        :returns: Business on a selected position, otherwise holiday.
        """
        selected = await self.selected_dates(d.year, d.month)
        return DayType.BusinessDay if d in selected else DayType.Holiday

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the base calendar ID.

        :returns: Immutable one-ID dependency set.
        """
        return frozenset((self.base_calendar.calendar_id,))

    def business_days(self) -> Self:
        """Return this total selector unchanged.

        :returns: This calendar instance.
        """
        return self


def nth_business_day_of_month(
    calendar: BDCalendar,
    *n: int,
) -> NthBusinessDayOfMonthBDCalendar | NthDayOfMonthBDCalendar:
    """Create a signed nth-business-day selector.

    :param calendar: Calendar defining business dates.
    :param n: Positions from ``-31..-1`` or ``1..31``.
    :returns: Nth calendar-day selector for ``ALL_DAYS`` or business-day selector.
    """
    values = canonical_nth(n)
    if calendar is ALL_DAYS:
        return nth_day_of_month(*values)
    return NthBusinessDayOfMonthBDCalendar(calendar, values)
