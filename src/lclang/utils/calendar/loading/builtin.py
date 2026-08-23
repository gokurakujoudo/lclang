"""Builtin singleton calendar loader."""

from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.builtins.registry import BUILTIN_CALENDARS
from lclang.utils.calendar.loading.base import BDCalendarLoader
from lclang.utils.calendar.types import CalendarID


@final
class BuiltinBDCalendarLoader(BDCalendarLoader):
    """Resolve identifiers from :data:`BUILTIN_CALENDARS`."""

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

