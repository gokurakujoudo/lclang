"""Expected failures raised by the business-day calendar subsystem."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from lclang.utils.calendar.types import CalendarID

if TYPE_CHECKING:
    from lclang.utils.calendar.base import BDCalendar


class DateOperationOutOfScopeException(Exception):
    """Report that a calendar cannot resolve a date operation.

    :param source_date: Date from which the unsuccessful operation started.
    :param source_calendar: Calendar responsible for resolving the operation.
    """

    def __init__(self, source_date: date, source_calendar: BDCalendar) -> None:
        """Create an out-of-scope date failure.

        :param source_date: Date from which the unsuccessful operation started.
        :param source_calendar: Calendar responsible for resolving the operation.
        :returns: ``None``.
        """
        super().__init__(
            f"calendar {source_calendar.calendar_id!r} cannot resolve date {source_date}"
        )
        self.source_date = source_date
        self.source_calendar = source_calendar


class CalendarCannotLoadException(Exception):
    """Report that a named calendar could not be loaded.

    :param calendar_id: Identifier requested from a calendar manager or loader.
    """

    def __init__(self, calendar_id: CalendarID) -> None:
        """Create a named-calendar loading failure.

        :param calendar_id: Identifier requested from a calendar manager or loader.
        :returns: ``None``.
        """
        super().__init__(f"cannot load calendar {calendar_id!r}")
        self.calendar_id = calendar_id


class CalendarLogicException(Exception):
    """Report an unexpected failure inside calendar logic.

    :param calendar_id: Identifier of the calendar whose logic failed.
    """

    def __init__(self, calendar_id: CalendarID) -> None:
        """Create a calendar-logic failure.

        :param calendar_id: Identifier of the calendar whose logic failed.
        :returns: ``None``.
        """
        super().__init__(f"calendar logic failed for {calendar_id!r}")
        self.calendar_id = calendar_id


class UnappliedCalendarOperationException(Exception):
    """Report an operation chain that has no source calendar."""

