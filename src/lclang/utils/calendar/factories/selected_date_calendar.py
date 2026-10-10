"""Sparse explicitly selected business-day factory.

Defines ``coerce_calendar_date``, ``FewBusinessDaysBDCalendar``, ``at``.
"""

from datetime import date
from typing import Self, final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.hardcoded_calendar import HardcodedBDCalendar


@guard_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
def coerce_calendar_date(value: date | str | int) -> date:
    """Convert one factory value into a strict Gregorian date.

    :param value: Date, strict ``YYYYMMDD`` text, or padded integer.
    :returns: Converted date.
    :raises LclValidationError: If *value* has an unsupported type.
    :raises LclValidationError: If an integer or string is not a valid date.
    """
    from lclang.lang.stdlib.date_conversion import parse_ymd

    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_ymd(value)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        text = f"{value:08d}"
        if len(text) == 8:
            return parse_ymd(text)
        raise LclValidationError(
            "integer calendar date must fit YYYYMMDD",
            code=UtilityErrorCode.E15_INTEGER_CALENDAR_DATE_MUST_FIT_YYYYMMDD,
        )
    raise LclValidationError(
        "calendar date must be date, YYYYMMDD text, or integer",
        code=UtilityErrorCode.E15_CALENDAR_DATE_MUST_BE_DATE_YYYYMMDD_TEXT_OR_INTEGER,
    )


@guard_constructor(LclValidationError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
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
        from lclang.lang.stdlib.date_conversion import to_ymd

        self.business_day_values = business_days
        identifier = CalendarID(f"at({', '.join(to_ymd(d) for d in business_days)})")
        super().__init__(identifier, {d: DayType.BusinessDay for d in business_days})

    @guard_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
    def business_days(self) -> Self:
        """Return this already-sparse business calendar.

        :returns: This calendar instance.
        """
        return self


@guard_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
def at(*values: date | str | int) -> FewBusinessDaysBDCalendar:
    """Create a calendar at explicitly selected business dates.

    :param values: Date, ``YYYYMMDD`` text, or integer values.
    :returns: Canonical finite business-day calendar.
    """
    dates = tuple(sorted({coerce_calendar_date(value) for value in values}))
    return FewBusinessDaysBDCalendar(dates)
