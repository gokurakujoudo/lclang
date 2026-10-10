"""Validated operand ordering for calendar composition.

Defines ``canonical_calendars``, ``ordered_calendars``.
"""

from collections.abc import Iterable

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID


@guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
def canonical_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID and sorted canonically.

    :param values: Calendar operands to normalize.
    :returns: Stable tuple ordered by calendar ID.
    :raises LclValidationError: If an operand is not a calendar.
    :raises LclValidationError: If no operands are supplied.
    """
    return tuple(sorted(ordered_calendars(values), key=lambda item: item.calendar_id))


@guard_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
def ordered_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID in encounter order.

    :param values: Ordered fallback operands.
    :returns: Stable encounter-order tuple.
    :raises LclValidationError: If an operand is not a calendar.
    :raises LclValidationError: If no operands are supplied.
    """
    by_id: dict[CalendarID, BDCalendar] = {}
    for calendar in values:
        if not isinstance(calendar, BDCalendar):
            raise LclValidationError(
                "calendar composition requires BDCalendar values",
                code=UtilityErrorCode.E14_CALENDAR_COMPOSITION_REQUIRES_BDCALENDAR_VALUES,
            )
        by_id.setdefault(calendar.calendar_id, calendar)
    if not by_id:
        raise LclValidationError(
            "calendar composition requires at least one operand",
            code=UtilityErrorCode.E14_CALENDAR_COMPOSITION_REQUIRES_AT_LEAST_ONE_OPERAND,
        )
    return tuple(by_id.values())
