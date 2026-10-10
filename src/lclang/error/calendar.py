"""Expected failures raised by the business-day calendar subsystem."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, cast

from lclang.error.base import LclError, LclValidationError
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.error.families import LclUtilityError
from lclang.error.wrapping import wrap_failure

if TYPE_CHECKING:
    from lclang.utils.calendar.base import BDCalendar
    from lclang.utils.calendar.types import CalendarID


class DateOperationOutOfScopeException(LclUtilityError):
    """Report that a calendar cannot resolve a date operation.

    :param source_date: Date from which the unsuccessful operation started.
    :param code: Optional classified failure code.
    :param source_calendar: Calendar responsible for resolving the operation.
    """

    default_code = str(utilities_codes.E11_D)

    def __init__(
        self, source_date: date, source_calendar: BDCalendar, *, code: str | None = None
    ) -> None:
        """Create an out-of-scope date failure.

        :param source_date: Date from which the unsuccessful operation started.
        :param code: Optional classified failure code.
        :param source_calendar: Calendar responsible for resolving the operation.
        :returns: ``None``.
        :raises LclValidationError: If a diagnostic constructor field is invalid.
        """
        if not isinstance(source_date, date):
            raise LclValidationError(
                "source date must be a date",
                code=utilities_codes.E11_HARDCODED_CALENDAR_KEYS_MUST_BE_DATES,
            )
        if not isinstance(getattr(source_calendar, "calendar_id", None), str):
            raise LclValidationError(
                "source calendar must expose a calendar ID",
                code=utilities_codes.CALENDAR_REFERENCE_TYPE,
            )
        super().__init__(
            f"calendar {source_calendar.calendar_id!r} cannot resolve date {source_date}", code=code
        )
        self.source_date = source_date
        self.source_calendar = source_calendar


class CalendarCannotLoadException(LclUtilityError):
    """Report that a named calendar could not be loaded.

    :param code: Optional classified failure code.
    :param calendar_id: Identifier requested from a calendar manager or loader.
    """

    default_code = str(utilities_codes.E12_LOAD_CALENDAR_FAILURE)

    def __init__(self, calendar_id: CalendarID, *, code: str | None = None) -> None:
        """Create a named-calendar loading failure.

        :param code: Optional classified failure code.
        :param calendar_id: Identifier requested from a calendar manager or loader.
        :returns: ``None``.
        :raises LclValidationError: If a diagnostic constructor field is invalid.
        """
        validate_calendar_error_id(calendar_id)
        super().__init__(f"cannot load calendar {calendar_id!r}", code=code)
        self.calendar_id = calendar_id


class CalendarLogicException(LclUtilityError):
    """Report an unexpected failure inside calendar logic.

    :param code: Optional classified failure code.
    :param calendar_id: Identifier of the calendar whose logic failed.
    """

    default_code = str(utilities_codes.E11_SELF_CALENDAR_ID)

    def __init__(self, calendar_id: CalendarID, *, code: str | None = None) -> None:
        """Create a calendar-logic failure.

        :param code: Optional classified failure code.
        :param calendar_id: Identifier of the calendar whose logic failed.
        :returns: ``None``.
        :raises LclValidationError: If a diagnostic constructor field is invalid.
        """
        validate_calendar_error_id(calendar_id)
        super().__init__(f"calendar logic failed for {calendar_id!r}", code=code)
        self.calendar_id = calendar_id


class UnappliedCalendarOperationException(LclUtilityError):
    """Report an operation chain that has no source calendar."""

    default_code = str(utilities_codes.E13_OPERATION_IS_UNAVAILABLE)

    def __init__(self, *, code: str | None = None) -> None:
        """Create a missing-source calendar failure.

        :param code: Optional classified failure code.
        """
        super().__init__("calendar mapping has no source calendar", code=code)


def validate_calendar_error_id(value: str) -> None:
    """Validate a diagnostic's calendar identifier without loading a calendar.

    :param value: Identifier retained in the calendar failure.
    :raises LclValidationError: If the identifier is not nonempty text.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "calendar ID must be text", code=utilities_codes.E11_CALENDAR_ID_MUST_BE_TEXT
        )
    if not value:
        raise LclValidationError(
            "calendar ID cannot be empty", code=utilities_codes.E11_CALENDAR_ID_CANNOT_BE_EMPTY
        )


def wrap_calendar_failure(error: Exception, failure: LclUtilityError) -> LclError:
    """Retain grouped calendar failures or attach a cause to the calendar's failure.

    :param error: Original callback or calendar-operation failure.
    :param failure: Calendar exception retaining its ID and selected concrete code.
    :returns: Calendar failure or structured group preserving members and context.
    """
    if isinstance(error, ExceptionGroup):
        grouped = wrap_failure(
            cast(ExceptionGroup[Exception], error),
            LclUtilityError,
            failure.code,
            message=failure.message,
        )
        note = failure.message
        if note not in getattr(grouped, "__notes__", ()):
            grouped.add_note(note)
        return grouped
    failure.__cause__ = error
    failure.__traceback__ = error.__traceback__
    if not isinstance(error, LclError):
        failure.freeze_native_cause(error)
    return failure
