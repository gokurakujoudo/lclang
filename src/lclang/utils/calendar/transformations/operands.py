"""Validated operand ordering for calendar composition."""

from collections.abc import Iterable

from lclang.error import LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.types import CalendarID


@guard_failure(LclUtilityError, utilities_codes.NATIVE_714)
def canonical_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID and sorted canonically.

    :param values: Calendar operands to normalize.
    :returns: Stable tuple ordered by calendar ID.
    :raises LclValidationError: If an operand is not a calendar.
    :raises LclValidationError: If no operands are supplied.
    """
    return tuple(sorted(ordered_calendars(values), key=lambda item: item.calendar_id))


@guard_failure(LclUtilityError, utilities_codes.NATIVE_714)
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
                code=utilities_codes.E14_CALENDAR_COMPOSITION_REQUIRES_BDCALENDAR_VALUES,
            )
        by_id.setdefault(calendar.calendar_id, calendar)
    if not by_id:
        raise LclValidationError(
            "calendar composition requires at least one operand",
            code=utilities_codes.E14_CALENDAR_COMPOSITION_REQUIRES_AT_LEAST_ONE_OPERAND,
        )
    return tuple(by_id.values())
