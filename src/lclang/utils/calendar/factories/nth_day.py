"""Nth-calendar-day-of-month factory."""

from calendar import monthrange
from datetime import date
from typing import Self, final

from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


def canonical_nth(values: tuple[int, ...]) -> tuple[int, ...]:
    """Validate and canonicalize signed month positions.

    :param values: Signed one-based month positions.
    :returns: Sorted unique positions.
    :raises TypeError: If a value is not an integer.
    :raises ValueError: If a value is zero or outside signed month bounds.
    """
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise TypeError("nth values must be integers")
    if any(value == 0 or not -31 <= value <= 31 for value in values):
        raise ValueError("nth values must be -31..-1 or 1..31")
    return tuple(sorted(set(values)))


def selected_month_days(year: int, month: int, nth: tuple[int, ...]) -> frozenset[int]:
    """Resolve signed positions to valid day numbers for one month.

    :param year: Gregorian year.
    :param month: Month number.
    :param nth: Canonical signed positions.
    :returns: Valid selected day numbers.
    """
    size = monthrange(year, month)[1]
    return frozenset(
        value if value > 0 else size + value + 1
        for value in nth
        if (value > 0 and value <= size) or (value < 0 and -value <= size)
    )


@final
class NthDayOfMonthBDCalendar(FunctionalBDCalendar):
    """Classify selected signed calendar-day positions as business.

    :param nth: Signed month positions.
    """

    __slots__ = ("nth",)

    def __init__(self, nth: tuple[int, ...]) -> None:
        """Create a canonical nth-day calendar.

        :param nth: Canonical signed month positions.
        :returns: ``None``.
        """
        self.nth = nth
        super().__init__(CalendarID(f"nth_day_of_month({', '.join(map(str, nth))})"))

    async def get_day_type(self, d: date) -> DayType:
        """Classify a date by its signed month positions.

        :param d: Date to classify.
        :returns: Business on a selected position, otherwise holiday.
        """
        selected = selected_month_days(d.year, d.month, self.nth)
        return DayType.BusinessDay if d.day in selected else DayType.Holiday

    def business_days(self) -> Self:
        """Return this total selector unchanged.

        :returns: This calendar instance.
        """
        return self


def nth_day_of_month(*n: int) -> NthDayOfMonthBDCalendar:
    """Create a signed nth-calendar-day selector.

    :param n: Positions from ``-31..-1`` or ``1..31``.
    :returns: Canonical nth-day calendar.
    """
    return NthDayOfMonthBDCalendar(canonical_nth(n))
