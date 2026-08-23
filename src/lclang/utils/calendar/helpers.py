"""Shared validation and safe date traversal helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Iterator
from datetime import date, timedelta
from inspect import isawaitable
from typing import TYPE_CHECKING, cast

from lclang.utils.calendar.errors import (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
from lclang.utils.calendar.types import DayType

if TYPE_CHECKING:
    from lclang.utils.calendar.base import BDCalendar

CALENDAR_ERRORS = (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
"""Calendar failures that must propagate without another wrapper."""


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
        raise CalendarLogicException(calendar.calendar_id) from error


def require_calendar_date(value: object) -> date:
    """Return an exact navigation date or reject an invalid result.

    :param value: Candidate navigation result.
    :returns: Validated date.
    :raises TypeError: If *value* is not a :class:`datetime.date`.
    """
    if not isinstance(value, date):
        raise TypeError("calendar navigation must return a date")
    return value


async def resolve_result[Result](value: Result | Awaitable[Result]) -> Result:
    """Resolve a possibly asynchronous calendar callback result.

    :param value: Immediate or awaitable callback result.
    :returns: Resolved immediate result.
    """
    if isawaitable(value):
        return await cast(Awaitable[Result], value)
    return value


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
    :raises ValueError: If *year* is outside the supported date range.
    """
    if not isinstance(year, int) or isinstance(year, bool) or not 1 <= year <= 9999:
        raise ValueError("calendar year must be between 1 and 9999")
    current = date(year, 1, 1)
    while current.year == year:
        yield current
        shifted = safe_add_days(current, 1)
        if shifted is None:
            return
        current = shifted


def require_day_type(value: object) -> DayType:
    """Return an exact day type or reject an invalid classifier result.

    :param value: Candidate classifier result.
    :returns: Validated day type.
    :raises TypeError: If *value* is not :class:`DayType`.
    """
    if not isinstance(value, DayType):
        raise TypeError("calendar classifier must return DayType")
    return value
