"""Calendar manager contracts."""

import asyncio
from collections.abc import Set
from typing import cast

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BDCalendarLoader,
    BDCalendarManager,
    BuiltinBDCalendarLoader,
    CalendarCannotLoadException,
    CalendarID,
    CalendarLogicException,
    DayType,
    HardcodedBDCalendar,
    def_functional_calendar,
    use_calendar_manager,
)
from tests.utils.calendar.calendar_support import (
    CancelledLoader,
    CountingLoader,
    DictionaryLoader,
    FixedLoader,
    FlakyLoader,
    GateLoader,
    RecursiveLoader,
)


@pytest.mark.asyncio
async def test_manager_validation_cycles_failures_and_retirement() -> None:
    """Manager covers validation, recursion, loader failures, and replacements."""
    with pytest.raises(TypeError):
        BDCalendarManager((cast(BDCalendarLoader, object()),))
    manager = use_calendar_manager(())
    for invalid in (cast(CalendarID, 1), CalendarID("")):
        with pytest.raises(TypeError):
            await manager.use_calendar(invalid)
    assert await manager.use_calendar(CalendarID("ALL_DAYS")) is ALL_DAYS
    assert await manager.use_calendar(CalendarID("ALL_DAYS")) is ALL_DAYS
    assert await manager.use_calendar(CalendarID("UNKNOWN"), CalendarID("ALL_DAYS")) is ALL_DAYS
    assert len(use_calendar_manager((BuiltinBDCalendarLoader(),)).loaders) == 1
    assert await manager.retire_calendar(CalendarID("NOT_CACHED")) == set()
    with pytest.raises(asyncio.CancelledError):
        await BDCalendarManager((CancelledLoader(),)).use_calendar(CalendarID("CANCEL"))
    with pytest.raises(CalendarCannotLoadException):
        await BDCalendarManager((RecursiveLoader(),)).use_calendar(CalendarID("LOOP"))
    ordinary = BDCalendarManager(
        (DictionaryLoader({CalendarID("FAIL"): RuntimeError("boom")}),)
    )
    with pytest.raises(CalendarCannotLoadException) as ordinary_failure:
        await ordinary.use_calendar(CalendarID("FAIL"))
    assert isinstance(ordinary_failure.value.__cause__, RuntimeError)
    domain = BDCalendarManager(
        (
            DictionaryLoader(
                {CalendarID("FAIL"): CalendarCannotLoadException(CalendarID("FAIL"))}
            ),
        )
    )
    with pytest.raises(CalendarCannotLoadException):
        await domain.use_calendar(CalendarID("FAIL"))
    mismatched = BDCalendarManager(
        (DictionaryLoader({CalendarID("WANTED"): ALL_DAYS}),)
    )
    with pytest.raises(CalendarCannotLoadException) as mismatch:
        await mismatched.use_calendar(CalendarID("WANTED"))
    assert isinstance(mismatch.value.__cause__, ValueError)
    assert await manager.retire_calendar(CalendarID("NONE"), ALL_WEEKDAYS) == set()
    assert manager.cached_calendars[CalendarID("NONE")] is ALL_WEEKDAYS

    derived = ALL_DAYS + ALL_WEEKDAYS
    retire = use_calendar_manager((DictionaryLoader({derived.calendar_id: derived}),))
    await retire.use_calendar(CalendarID("ALL_DAYS"))
    await retire.use_calendar(derived.calendar_id)
    removed = await retire.retire_calendar(CalendarID("ALL_DAYS"), ALL_WEEKDAYS)
    assert removed == {CalendarID("ALL_DAYS"), derived.calendar_id}
    assert retire.cached_calendars[CalendarID("ALL_DAYS")] is ALL_WEEKDAYS

    def broken_dependencies() -> Set[CalendarID]:
        raise RuntimeError("dependency failure")

    broken = def_functional_calendar(
        CalendarID("BROKEN_DEPS"),
        lambda d: DayType.Holiday,
        broken_dependencies,
    )
    base = HardcodedBDCalendar(CalendarID("BASE"), {})
    retire_broken = BDCalendarManager(
        (DictionaryLoader({base.calendar_id: base, broken.calendar_id: broken}),)
    )
    await retire_broken.use_calendar(CalendarID("BASE"))
    await retire_broken.use_calendar(broken.calendar_id)
    with pytest.raises(CalendarLogicException):
        await retire_broken.retire_calendar(CalendarID("BASE"))


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
