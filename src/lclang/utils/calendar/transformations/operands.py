"""Validated operand ordering for calendar composition."""
from collections.abc import Iterable

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.types import CalendarID


def canonical_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID and sorted canonically.

    :param values: Calendar operands to normalize.
    :returns: Stable tuple ordered by calendar ID.
    :raises TypeError: If an operand is not a calendar.
    :raises ValueError: If no operands are supplied.
    """
    return tuple(sorted(ordered_calendars(values), key=lambda item: item.calendar_id))

def ordered_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID in encounter order.

    :param values: Ordered fallback operands.
    :returns: Stable encounter-order tuple.
    :raises TypeError: If an operand is not a calendar.
    :raises ValueError: If no operands are supplied.
    """
    by_id: dict[CalendarID, BDCalendar] = {}
    for calendar in values:
        if not isinstance(calendar, BDCalendar):
            raise TypeError("calendar composition requires BDCalendar values")
        by_id.setdefault(calendar.calendar_id, calendar)
    if not by_id:
        raise ValueError("calendar composition requires at least one operand")
    return tuple(by_id.values())
