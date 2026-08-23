"""Abstract named-calendar loader contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.types import CalendarID

if TYPE_CHECKING:
    from lclang.utils.calendar.loading.manager import BDCalendarManager


class BDCalendarLoader(ABC):
    """Load calendars handled by one named source."""

    @abstractmethod
    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        """Load one calendar or decline the identifier.

        :param calendar_id: Requested calendar identifier.
        :param manager: Manager available for loading dependencies.
        :returns: Loaded calendar, or ``None`` when this loader does not handle it.
        :raises CalendarCannotLoadException: If handled content cannot be loaded.
        """

