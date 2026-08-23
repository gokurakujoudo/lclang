"""Behavioral tests for strict JSON loading and calendar management."""

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BDCalendar,
    BDCalendarLoader,
    BDCalendarManager,
    CalendarCannotLoadException,
    CalendarID,
    DayType,
    HardcodedBDCalendar,
    at,
    use_calendar_manager,
    use_file_system_hardcoded_calendar_loader,
)


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


@pytest.mark.asyncio
async def test_filesystem_loader_accepts_strict_json_and_rejects_bad_content(
    tmp_path: Path,
) -> None:
    """Filesystem loading parses strict date arrays and preserves causes."""
    good = tmp_path / "MARKET.calendar.json"
    good.write_text(
        json.dumps({"business_days": ["20240102"], "holidays": ["20240101"]}),
        encoding="utf-8",
    )
    loader = use_file_system_hardcoded_calendar_loader(tmp_path)
    manager = use_calendar_manager((loader,))
    calendar = await manager.use_calendar(CalendarID("MARKET"))
    assert await calendar.get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
    assert await calendar.get_day_type(date(2024, 1, 1)) is DayType.Holiday
    bad = tmp_path / "BAD.calendar.json"
    bad.write_text('{"business_days": [], "holidays": [], "extra": []}', encoding="utf-8")
    with pytest.raises(CalendarCannotLoadException) as failure:
        await manager.use_calendar(CalendarID("BAD"))
    assert isinstance(failure.value.__cause__, ValueError)
    with pytest.raises(CalendarCannotLoadException):
        await manager.use_calendar(CalendarID("MISSING"))


@pytest.mark.asyncio
async def test_manager_singleflight_fallback_builtin_and_retirement() -> None:
    """Manager shares loads, preserves singleton identity, and retires dependants."""
    loader = CountingLoader()
    manager = use_calendar_manager((loader,))
    first, second = await asyncio.gather(
        manager.use_calendar(CalendarID("at(20240102)")),
        manager.use_calendar(CalendarID("at(20240102)")),
    )
    assert first is second and loader.calls == 1
    assert await manager.use_calendar(CalendarID("ALL_DAYS")) is ALL_DAYS
    assert await manager.use_calendar(CalendarID("UNKNOWN"), ALL_WEEKDAYS) is ALL_WEEKDAYS
    derived = ALL_DAYS + ALL_WEEKDAYS
    retiring = use_calendar_manager((FixedLoader(derived),))
    await retiring.use_calendar(CalendarID("ALL_DAYS"))
    await retiring.use_calendar(derived.calendar_id)
    assert await retiring.use_calendar(CalendarID("ALL_WEEKDAYS")) is ALL_WEEKDAYS
    removed = await retiring.retire_calendar(CalendarID("ALL_DAYS"))
    assert removed == {CalendarID("ALL_DAYS"), derived.calendar_id}
    assert retiring.cached_calendars[CalendarID("ALL_WEEKDAYS")] is ALL_WEEKDAYS


@pytest.mark.asyncio
async def test_manager_shields_shared_load_and_retries_after_failure() -> None:
    """Cancelling one waiter preserves the load; a failed flight remains retryable."""
    started = asyncio.Event()
    release = asyncio.Event()
    gate = GateLoader(started, release)
    manager = BDCalendarManager((gate,))
    first = asyncio.create_task(manager.use_calendar(CalendarID("SHARED")))
    await started.wait()
    second = asyncio.create_task(manager.use_calendar(CalendarID("SHARED")))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert (await second).calendar_id == CalendarID("SHARED")
    assert gate.calls == 1

    flaky = FlakyLoader()
    retrying = BDCalendarManager((flaky,))
    with pytest.raises(CalendarCannotLoadException):
        await retrying.use_calendar(CalendarID("RETRY"))
    assert (await retrying.use_calendar(CalendarID("RETRY"))).calendar_id == CalendarID(
        "RETRY"
    )
    assert flaky.calls == 2
