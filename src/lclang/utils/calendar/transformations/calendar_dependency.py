"""Shared logic for composed calendar implementations.

Defines ``dependency_day_type``, ``direct_dependency_ids``.
"""

from collections.abc import Iterable, Set
from datetime import date

from lclang.error import LclError, LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import CalendarLogicException, wrap_calendar_failure
from lclang.error.operation_guard import guard_async_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_date_operation import CALENDAR_ERRORS, require_day_type
from lclang.utils.calendar.calendar_type import CalendarID, DayType


@guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
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
                    else UtilityErrorCode.E14_DEPENDENCY_DAY_TYPE_FAILURE
                ),
            ),
        )
        raise failure from failure.__cause__


@guard_async_failure(LclUtilityError, UtilityErrorCode.E14_CALENDAR_COMPOSITION_NATIVE_FAILURE)
async def direct_dependency_ids(calendars: Iterable[BDCalendar]) -> Set[CalendarID]:
    """Return direct IDs for calendar operands.

    :param calendars: Direct dependency calendars.
    :returns: Immutable set of their IDs.
    """
    return frozenset(calendar.calendar_id for calendar in calendars)
