"""Abstract named-calendar loader contract.

Defines ``BDCalendarLoader``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.operation_guard import guard_async_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID

if TYPE_CHECKING:
    from lclang.utils.calendar.loading.calendar_manager import BDCalendarManager


class BDCalendarLoader(ABC):
    """Load calendars handled by one named source."""

    @abstractmethod
    @guard_async_failure(LclUtilityError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
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
