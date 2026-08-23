"""Sparse explicitly selected business-day factory."""

from datetime import date
from typing import Self, final

from lclang.stdlib.dates import parse_ymd, to_ymd
from lclang.utils.calendar.hardcoded import HardcodedBDCalendar
from lclang.utils.calendar.types import CalendarID, DayType


def coerce_calendar_date(value: date | str | int) -> date:
    """Convert one factory value into a strict Gregorian date.

    :param value: Date, strict ``YYYYMMDD`` text, or padded integer.
    :returns: Converted date.
    :raises TypeError: If *value* has an unsupported type.
    :raises ValueError: If an integer or string is not a valid date.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_ymd(value)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        text = f"{value:08d}"
        if len(text) == 8:
            return parse_ymd(text)
        raise ValueError("integer calendar date must fit YYYYMMDD")
    raise TypeError("calendar date must be date, YYYYMMDD text, or integer")


@final
class FewBusinessDaysBDCalendar(HardcodedBDCalendar):
    """Classify only a finite set of dates as business.

    :param business_days: Dates to retain as business days.
    """

    __slots__ = ("business_day_values",)

    def __init__(self, business_days: tuple[date, ...]) -> None:
        """Create a canonical finite business-day calendar.

        :param business_days: Sorted unique business dates.
        :returns: ``None``.
        """
        self.business_day_values = business_days
        identifier = CalendarID(f"at({', '.join(to_ymd(d) for d in business_days)})")
        super().__init__(identifier, {d: DayType.BusinessDay for d in business_days})

    def business_days(self) -> Self:
        """Return this already-sparse business calendar.

        :returns: This calendar instance.
        """
        return self


def at(*values: date | str | int) -> FewBusinessDaysBDCalendar:
    """Create a calendar at explicitly selected business dates.

    :param values: Date, ``YYYYMMDD`` text, or integer values.
    :returns: Canonical finite business-day calendar.
    """
    dates = tuple(sorted({coerce_calendar_date(value) for value in values}))
    return FewBusinessDaysBDCalendar(dates)

