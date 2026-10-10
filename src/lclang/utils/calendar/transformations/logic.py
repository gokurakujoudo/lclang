"""Shared logic for composed calendar implementations."""

from collections.abc import Iterable, Set
from datetime import date

from lclang.error import LclError, LclUtilityError
from lclang.error.boundary import guard_async_failure
from lclang.error.calendar import CalendarLogicException, wrap_calendar_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.helpers import CALENDAR_ERRORS, require_day_type
from lclang.utils.calendar.types import CalendarID, DayType


@guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
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
        failure = wrap_calendar_failure(
            error,
            CalendarLogicException(
                calendar.calendar_id,
                code=(
                    error.code
                    if isinstance(error, LclError)
                    else utilities_codes.E14_DEPENDENCY_DAY_TYPE_FAILURE
                ),
            ),
        )
        raise failure from failure.__cause__


@guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
async def direct_dependency_ids(calendars: Iterable[BDCalendar]) -> Set[CalendarID]:
    """Return direct IDs for calendar operands.

    :param calendars: Direct dependency calendars.
    :returns: Immutable set of their IDs.
    """
    return frozenset(calendar.calendar_id for calendar in calendars)
