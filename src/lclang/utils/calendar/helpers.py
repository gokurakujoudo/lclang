"""Shared validation and safe date traversal helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Iterator
from datetime import date, timedelta
from inspect import isawaitable
from typing import TYPE_CHECKING, cast

from lclang.error import LclError, LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_failure
from lclang.error.calendar import (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
    wrap_calendar_failure,
)
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.types import DayType

if TYPE_CHECKING:
    from lclang.utils.calendar.base import BDCalendar

# Unitless exception categories below come from the calendar error contract. These existing
# domain failures propagate unchanged while unexpected dependency failures receive calendar
# context.
CALENDAR_ERRORS = (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
"""Calendar failures that must propagate without another wrapper."""


@guard_async_failure(LclUtilityError, utilities_codes.NATIVE_719)
async def dependency_date(calendar: BDCalendar, value: Awaitable[date]) -> date:
    """Resolve and validate navigation through a dependency calendar.

    :param calendar: Calendar whose navigation is being awaited.
    :param value: Awaitable navigation result.
    :returns: Validated target date.
    :raises CalendarLogicException: If dependency navigation fails unexpectedly.
    """
    try:
        return require_calendar_date(await value)
    except CALENDAR_ERRORS:
        raise
    except Exception as error:
        failure = wrap_calendar_failure(
            error,
            CalendarLogicException(
                calendar.calendar_id,
                code=(
                    error.code
                    if isinstance(error, LclError)
                    else utilities_codes.E19_DEPENDENCY_DATE_FAILURE
                ),
            ),
        )
        raise failure from failure.__cause__


@guard_failure(LclUtilityError, utilities_codes.NATIVE_719)
def require_calendar_date(value: object) -> date:
    """Return an exact navigation date or reject an invalid result.

    :param value: Candidate navigation result.
    :returns: Validated date.
    :raises LclValidationError: If *value* is not a :class:`datetime.date`.
    """
    if not isinstance(value, date):
        raise LclValidationError(
            "calendar navigation must return a date",
            code=utilities_codes.E19_CALENDAR_NAVIGATION_MUST_RETURN_A_DATE,
        )
    return value


@guard_async_failure(LclUtilityError, utilities_codes.NATIVE_719)
async def resolve_result[Result](value: Result | Awaitable[Result]) -> Result:
    """Resolve a possibly asynchronous calendar callback result.

    :param value: Immediate or awaitable callback result.
    :returns: Resolved immediate result.
    """
    if isawaitable(value):
        return await cast(Awaitable[Result], value)
    return value


@guard_failure(LclUtilityError, utilities_codes.NATIVE_719)
def safe_add_days(d: date, days: int) -> date | None:
    """Add calendar days without overflowing :class:`datetime.date`.

    :param d: Source date.
    :param days: Signed calendar-day displacement.
    :returns: Shifted date, or ``None`` when it is outside the date range.
    """
    try:
        return d + timedelta(days=days)
    except OverflowError:
        return None


def year_dates(year: int) -> Iterator[date]:
    """Iterate every Gregorian date in one supported year.

    :param year: Year from 1 through 9999.
    :returns: Iterator over every date in the year.
    :raises LclValidationError: If *year* is outside the supported date range.
    """
    if not isinstance(year, int) or isinstance(year, bool) or not 1 <= year <= 9999:
        raise LclValidationError(
            "calendar year must be between 1 and 9999",
            code=utilities_codes.E19_CALENDAR_YEAR_MUST_BE_BETWEEN_1_AND_9999,
        )
    current = date(year, 1, 1)
    while current.year == year:
        yield current
        shifted = safe_add_days(current, 1)
        if shifted is None:
            return
        current = shifted


@guard_failure(LclUtilityError, utilities_codes.NATIVE_719)
def require_day_type(value: object) -> DayType:
    """Return an exact day type or reject an invalid classifier result.

    :param value: Candidate classifier result.
    :returns: Validated day type.
    :raises LclValidationError: If *value* is not :class:`DayType`.
    """
    if not isinstance(value, DayType):
        raise LclValidationError(
            "calendar classifier must return DayType",
            code=utilities_codes.E19_CALENDAR_CLASSIFIER_MUST_RETURN_DAYTYPE,
        )
    return value
