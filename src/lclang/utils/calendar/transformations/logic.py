"""Shared logic for composed calendar implementations."""

from collections.abc import Iterable, Set
from datetime import date

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import CalendarLogicException
from lclang.utils.calendar.helpers import CALENDAR_ERRORS, require_day_type
from lclang.utils.calendar.types import CalendarID, DayType


def canonical_calendars(values: Iterable[BDCalendar]) -> tuple[BDCalendar, ...]:
    """Return calendars deduplicated by ID and sorted canonically.

    :param values: Calendar operands to normalize.
    :returns: Stable tuple ordered by calendar ID.
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
    return tuple(by_id[key] for key in sorted(by_id))


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


async def dependency_day_type(calendar: BDCalendar, d: date) -> DayType:
    """Classify through a dependency with structured logic wrapping.

    :param calendar: Dependency calendar.
    :param d: Date to classify.
    :returns: Validated dependency day type.
    :raises CalendarLogicException: If dependency logic fails unexpectedly.
    """
    try:
        return require_day_type(await calendar.get_day_type(d))
    except CALENDAR_ERRORS:
        raise
    except Exception as error:
        raise CalendarLogicException(calendar.calendar_id) from error


async def direct_dependency_ids(calendars: Iterable[BDCalendar]) -> Set[CalendarID]:
    """Return direct IDs for calendar operands.

    :param calendars: Direct dependency calendars.
    :returns: Immutable set of their IDs.
    """
    return frozenset(calendar.calendar_id for calendar in calendars)

