"""Concurrent named-calendar loading and retirement manager."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping, Set
from contextvars import ContextVar
from types import MappingProxyType
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import CalendarCannotLoadException, CalendarLogicException
from lclang.utils.calendar.loading.base import BDCalendarLoader
from lclang.utils.calendar.loading.builtin import BuiltinBDCalendarLoader
from lclang.utils.calendar.types import CalendarID

# Task-local named-calendar dependency path used for cycle detection.
ACTIVE_CALENDAR_LOADS: ContextVar[tuple[CalendarID, ...]] = ContextVar(
    "active_calendar_loads", default=()
)


@final
class BDCalendarManager:
    """Coordinate calendar loaders, successful cache entries, and retirement.

    :param loaders: Ordered loader instances.
    """

    __slots__ = ("_cached_calendars", "_flights", "cached_calendars", "loaders")

    def __init__(self, loaders: Iterable[BDCalendarLoader]) -> None:
        """Create an empty manager cache with ordered loaders.

        :param loaders: Ordered loader instances.
        :returns: ``None``.
        :raises TypeError: If an item is not a calendar loader.
        """
        values = tuple(loaders)
        if any(not isinstance(loader, BDCalendarLoader) for loader in values):
            raise TypeError("calendar manager loaders must be BDCalendarLoader values")
        self.loaders = values
        self._cached_calendars: dict[CalendarID, BDCalendar] = {}
        self.cached_calendars: Mapping[CalendarID, BDCalendar] = MappingProxyType(
            self._cached_calendars
        )
        self._flights: dict[
            tuple[asyncio.AbstractEventLoop, CalendarID],
            asyncio.Task[BDCalendar | None],
        ] = {}

    async def use_calendar(
        self,
        calendar_id: CalendarID,
        fallback: BDCalendar | CalendarID | None = None,
    ) -> BDCalendar:
        """Return a cached, loaded, or fallback calendar.

        :param calendar_id: Requested calendar identifier.
        :param fallback: Calendar, calendar ID, or ``None``.
        :returns: Resolved calendar instance.
        :raises TypeError: If *calendar_id* is not non-empty text.
        :raises CalendarCannotLoadException: If no loader or fallback resolves it.
        """
        if not isinstance(calendar_id, str) or not calendar_id:
            raise TypeError("calendar ID must be non-empty text")
        selected_id = CalendarID(calendar_id)
        cached = self._cached_calendars.get(selected_id)
        if cached is not None:
            return cached
        if selected_id in ACTIVE_CALENDAR_LOADS.get():
            raise CalendarCannotLoadException(selected_id)
        flight_key = (asyncio.get_running_loop(), selected_id)
        task = self._flights.get(flight_key)
        if task is None:
            task = asyncio.create_task(self.load_named_calendar(selected_id))
            self._flights[flight_key] = task
        loaded = await asyncio.shield(task)
        if loaded is not None:
            return loaded
        if isinstance(fallback, BDCalendar):
            return fallback
        if isinstance(fallback, str):
            return await self.use_calendar(CalendarID(fallback))
        raise CalendarCannotLoadException(selected_id)

    async def load_named_calendar(self, calendar_id: CalendarID) -> BDCalendar | None:
        """Own one shared loader traversal and successful cache commit.

        :param calendar_id: Requested calendar identifier.
        :returns: Loaded calendar or ``None`` when every loader declines it.
        :raises CalendarCannotLoadException: If a loader fails or returns a wrong ID.
        """
        token = ACTIVE_CALENDAR_LOADS.set((*ACTIVE_CALENDAR_LOADS.get(), calendar_id))
        try:
            for loader in self.loaders:
                try:
                    calendar = await loader.load_calendar(calendar_id, self)
                except asyncio.CancelledError:
                    raise
                except CalendarCannotLoadException:
                    raise
                except Exception as error:
                    raise CalendarCannotLoadException(calendar_id) from error
                if calendar is None:
                    continue
                if calendar.calendar_id != calendar_id:
                    mismatch = ValueError("loader returned a mismatched calendar ID")
                    raise CalendarCannotLoadException(calendar_id) from mismatch
                self._cached_calendars[calendar_id] = calendar
                return calendar
            return None
        finally:
            ACTIVE_CALENDAR_LOADS.reset(token)
            current = asyncio.current_task()
            flight_key = (asyncio.get_running_loop(), calendar_id)
            if self._flights.get(flight_key) is current:
                self._flights.pop(flight_key, None)

    async def retire_calendar(
        self,
        calendar_id: CalendarID,
        replace_by: BDCalendar | None = None,
    ) -> Set[CalendarID]:
        """Drop a cached calendar and every recursive dependant.

        :param calendar_id: Cache key to retire.
        :param replace_by: Optional replacement stored beneath the retired key.
        :returns: Immutable set of removed cache keys.
        :raises CalendarLogicException: If dependency inspection fails unexpectedly.
        """
        if calendar_id not in self._cached_calendars:
            if replace_by is not None:
                self._cached_calendars[calendar_id] = replace_by
            return frozenset()
        removed: set[CalendarID] = {calendar_id}
        changed = True
        while changed:
            changed = False
            for key, calendar in tuple(self._cached_calendars.items()):
                if key in removed:
                    continue
                try:
                    dependencies = await calendar.get_dependency_ids()
                except Exception as error:
                    raise CalendarLogicException(calendar.calendar_id) from error
                if removed & set(dependencies):
                    removed.add(key)
                    changed = True
        for key in removed:
            self._cached_calendars.pop(key, None)
        if replace_by is not None:
            self._cached_calendars[calendar_id] = replace_by
        return frozenset(removed)


def use_calendar_manager(loaders: Iterable[BDCalendarLoader]) -> BDCalendarManager:
    """Create a manager with a builtin loader last.

    :param loaders: Ordered application loaders.
    :returns: Calendar manager with builtin fallback loading.
    """
    values = list(loaders)
    if not any(isinstance(loader, BuiltinBDCalendarLoader) for loader in values):
        values.append(BuiltinBDCalendarLoader())
    return BDCalendarManager(values)
