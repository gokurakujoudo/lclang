"""Reusable calendar failure and loader fixtures."""

import asyncio
from collections.abc import Mapping
from datetime import date
from typing import cast

from lclang.utils.calendar import (
    BDCalendar,
    BDCalendarLoader,
    BDCalendarManager,
    CalendarCannotLoadException,
    CalendarID,
    DateOperationOutOfScopeException,
    DayType,
    ForwardStepBDCalendar,
    FunctionalBDCalendar,
    HardcodedBDCalendar,
    YearBatchBDCalendar,
    at,
)


class DomainFailureCalendar(FunctionalBDCalendar):
    """Classifier that raises an existing calendar-domain failure."""

    async def get_day_type(self, d: date) -> DayType:
        raise DateOperationOutOfScopeException(d, self)


class InvalidForwardCalendar(ForwardStepBDCalendar):
    """Forward generator returning a configured invalid result."""

    def __init__(self, result: object) -> None:
        """Create a forward calendar returning *result*."""
        super().__init__(CalendarID("INVALID_FORWARD"), date(2024, 1, 1))
        self.result = result

    async def next_bd(self, d: date) -> date:
        if isinstance(self.result, Exception):
            raise self.result
        return cast(date, self.result)


class InvalidBatchCalendar(YearBatchBDCalendar):
    """Year loader returning configured malformed content."""

    def __init__(self, result: object) -> None:
        """Create a year-batch calendar returning *result*."""
        super().__init__(CalendarID("INVALID_BATCH"))
        self.result = result

    async def gen_year(self, year: int) -> dict[date, DayType]:
        if isinstance(self.result, Exception):
            raise self.result
        return cast(dict[date, DayType], self.result)


class DictionaryLoader(BDCalendarLoader):
    """Load calendars or configured failures from an in-memory mapping."""

    def __init__(self, values: Mapping[CalendarID, BDCalendar | Exception]) -> None:
        """Retain an immutable-by-convention result mapping."""
        self.values = values

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        del manager
        value = self.values.get(calendar_id)
        if isinstance(value, Exception):
            raise value
        return value


class RecursiveLoader(BDCalendarLoader):
    """Re-enter the manager for the same identifier."""

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        return await manager.use_calendar(calendar_id)


class CancelledLoader(BDCalendarLoader):
    """Cancel its owning manager load task."""

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        del calendar_id, manager
        raise asyncio.CancelledError


class RawFailureCalendar(FunctionalBDCalendar):
    """Raise an unexpected dependency-classification failure."""

    async def get_day_type(self, d: date) -> DayType:
        del d
        raise RuntimeError("raw dependency failure")


class SimpleForwardCalendar(ForwardStepBDCalendar):
    """Minimal forward subclass used to validate construction."""

    async def next_bd(self, d: date) -> date:
        raise DateOperationOutOfScopeException(d, self)


class CountingLoader(BDCalendarLoader):
    """Loader recording shared requests for concurrency tests."""

    def __init__(self) -> None:
        """Create an empty loader call count."""
        self.calls = 0

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        self.calls += 1
        await asyncio.sleep(0)
        return at("20240102") if calendar_id == CalendarID("at(20240102)") else None


class GateLoader(BDCalendarLoader):
    """Hold one successful load open while waiters are coordinated."""

    def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
        """Store synchronization gates and an empty call count."""
        self.started = started
        self.release = release
        self.calls = 0

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        del manager
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return HardcodedBDCalendar(calendar_id, {})


class FlakyLoader(BDCalendarLoader):
    """Fail one load and resolve the retry."""

    def __init__(self) -> None:
        """Create a loader with no attempts."""
        self.calls = 0

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        del manager
        self.calls += 1
        if self.calls == 1:
            raise CalendarCannotLoadException(calendar_id)
        return HardcodedBDCalendar(calendar_id, {})


class FixedLoader(BDCalendarLoader):
    """Return one configured calendar by its exact identity."""

    def __init__(self, calendar: BDCalendar) -> None:
        """Store the single calendar result."""
        self.calendar = calendar

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        del manager
        return self.calendar if calendar_id == self.calendar.calendar_id else None
