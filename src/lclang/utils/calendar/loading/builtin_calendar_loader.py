"""Builtin singleton calendar loader.

Defines ``BuiltinBDCalendarLoader``.
"""

from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.operation_guard import guard_async_failure
from lclang.utils.calendar.builtins.builtin_calendar_registry import BUILTIN_CALENDARS
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID
from lclang.utils.calendar.loading.calendar_loader import BDCalendarLoader


@final
class BuiltinBDCalendarLoader(BDCalendarLoader):
    """Resolve identifiers from :data:`BUILTIN_CALENDARS`."""

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: object,
    ) -> BDCalendar | None:
        """Return a canonical builtin singleton when present.

        :param calendar_id: Requested calendar identifier.
        :param manager: Unused manager retained for loader symmetry.
        :returns: Singleton calendar or ``None``.
        """
        del manager
        return BUILTIN_CALENDARS.get(calendar_id)
