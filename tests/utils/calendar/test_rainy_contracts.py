"""Rainy and boundary contracts for the complete calendar subsystem."""

import asyncio
import json
from collections.abc import Callable, Mapping, Set
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BEGIN_OF_YEARS,
    END_OF_YEARS,
    SELF_CALENDAR,
    BDCalendar,
    BDCalendarLoader,
    BDCalendarManager,
    BDCalendarMapping,
    BuiltinBDCalendarLoader,
    CalendarCannotLoadException,
    CalendarID,
    CalendarLogicException,
    CalendarMapBDCalendar,
    DateOperationOutOfScopeException,
    DayType,
    FileSystemHardcodedBDCalendarLoader,
    ForwardStepBDCalendar,
    FunctionalBDCalendar,
    HardcodedBDCalendar,
    ShiftNDaysMapOperation,
    SubtractionBDCalendar,
    ThisOrNextMapOperation,
    ThisOrPrevMapOperation,
    UnappliedCalendarOperationException,
    WeekdayBDCalendar,
    YearBatchBDCalendar,
    at,
    def_functional_calendar,
    nth_business_day_of_month,
    nth_day_of_month,
    range_end_days,
    range_start_days,
    use_calendar_manager,
)
from lclang.utils.calendar.loading.filesystem import read_calendar_json
from lclang.utils.calendar.transformations.logic import (
    canonical_calendars,
    dependency_day_type,
    direct_dependency_ids,
    ordered_calendars,
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


@pytest.mark.asyncio
async def test_core_validation_and_boundary_search_failures() -> None:
    """Core strategies reject invalid identity, mapping, and date boundaries."""
    with pytest.raises(TypeError):
        HardcodedBDCalendar(cast(CalendarID, 1), {})
    with pytest.raises(ValueError):
        HardcodedBDCalendar(CalendarID(""), {})
    with pytest.raises(TypeError):
        HardcodedBDCalendar(CalendarID("BAD"), {cast(date, "bad"): DayType.Holiday})
    with pytest.raises(TypeError):
        HardcodedBDCalendar(CalendarID("BAD"), {date.today(): cast(DayType, "bad")})
    empty = HardcodedBDCalendar(CalendarID("EMPTY"), {})
    with pytest.raises(DateOperationOutOfScopeException):
        await empty.prev_bd(date.today())
    assert await empty.business_days().get_day_type(date.today()) is DayType.Undefined
    total = DomainFailureCalendar(CalendarID("DOMAIN"))
    with pytest.raises(DateOperationOutOfScopeException):
        await total.cached_day_type(date.today())
    with pytest.raises(DateOperationOutOfScopeException):
        await ALL_WEEKDAYS.next_bd(date.max)
    with pytest.raises(DateOperationOutOfScopeException):
        await ALL_WEEKDAYS.prev_bd(date.min)
    assert await ALL_WEEKDAYS.map_this_or_prev().map_date(date(2024, 1, 7)) == date(
        2024, 1, 5
    )
    assert len(await ALL_DAYS.gen_year(9999)) == 365

    total_holiday = def_functional_calendar(
        CalendarID("TOTAL_HOLIDAY"), lambda d: DayType.Holiday
    )
    with pytest.raises(DateOperationOutOfScopeException):
        await total_holiday.next_bd(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await total_holiday.prev_bd(date(2024, 1, 1))


@pytest.mark.asyncio
async def test_forward_and_year_batch_reject_malformed_generation() -> None:
    """Generated strategies wrap unexpected results and preserve domain failures."""
    with pytest.raises(TypeError):
        SimpleForwardCalendar(CalendarID("BAD"), cast(date, "bad"))
    for result in (date(2024, 1, 1), "bad", RuntimeError("boom")):
        calendar = InvalidForwardCalendar(result)
        with pytest.raises(CalendarLogicException):
            await calendar.cache_through(date(2024, 1, 2))
    domain = InvalidForwardCalendar(DateOperationOutOfScopeException(date.today(), ALL_DAYS))
    await domain.cache_through(date(2024, 1, 2))
    assert domain.fully_cached
    with pytest.raises(DateOperationOutOfScopeException):
        await domain.prev_bd(date(2024, 1, 1))
    assert await domain.get_day_type(date(2023, 12, 31)) is DayType.Undefined
    assert await domain.gen_year(2023) == {}
    assert domain.defined_business_days == (date(2024, 1, 1),)
    propagated = InvalidForwardCalendar(CalendarCannotLoadException(CalendarID("LOAD")))
    with pytest.raises(CalendarCannotLoadException):
        await propagated.cache_through(date(2024, 1, 2))

    invalid_batches: tuple[object, ...] = (
        [],
        {date(2023, 1, 1): DayType.Holiday},
        {cast(date, "bad"): DayType.Holiday},
        {date(2024, 1, 1): cast(DayType, "bad")},
        RuntimeError("boom"),
    )
    for batch_result in invalid_batches:
        with pytest.raises(CalendarLogicException):
            await InvalidBatchCalendar(batch_result).loaded_year(2024)
    undefined = InvalidBatchCalendar({date(2024, 1, 1): DayType.Undefined})
    assert await undefined.loaded_year(2024) == {}
    assert await undefined.loaded_year(2024) is await undefined.loaded_year(2024)
    with pytest.raises(DateOperationOutOfScopeException):
        await undefined.next_bd(date.max)
    with pytest.raises(DateOperationOutOfScopeException):
        await undefined.prev_bd(date.min)
    propagated_batch = InvalidBatchCalendar(
        CalendarCannotLoadException(CalendarID("BATCH"))
    )
    with pytest.raises(CalendarCannotLoadException):
        await propagated_batch.loaded_year(2024)
    empty_batch = InvalidBatchCalendar({})
    with pytest.raises(DateOperationOutOfScopeException):
        await empty_batch.next_bd(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await empty_batch.prev_bd(date(2024, 1, 1))


@pytest.mark.asyncio
async def test_all_transformation_branches_and_dependency_wrapping() -> None:
    """Composition covers sparse truth tables, dependencies, and invalid operands."""
    d = date(2024, 1, 2)
    business = at(d)
    holiday = nth_day_of_month(1)
    undefined = at()
    assert await (business + holiday).get_day_type(date(2024, 1, 3)) is DayType.Holiday
    assert await (undefined & undefined).get_day_type(d) is DayType.Undefined
    intersection = business & ALL_DAYS
    assert await intersection.get_day_type(d) is DayType.BusinessDay
    assert await intersection.get_dependency_ids() == {
        CalendarID("ALL_DAYS"),
        business.calendar_id,
    }
    assert await (undefined >> at()).get_day_type(d) is DayType.Undefined
    assert await (undefined >> business).get_dependency_ids() == {
        undefined.calendar_id,
        business.calendar_id,
    }
    reverted = ~business
    assert await reverted.get_day_type(d) is DayType.Holiday
    assert await reverted.get_day_type(date(2024, 1, 3)) is DayType.Undefined
    assert await reverted.get_dependency_ids() == {business.calendar_id}
    assert await (~ALL_WEEKDAYS).get_day_type(date(2024, 1, 6)) is DayType.BusinessDay
    only_business = ALL_WEEKDAYS.business_days()
    assert await only_business.get_day_type(d) is DayType.BusinessDay
    assert only_business.business_days() is only_business
    assert await only_business.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    only_holiday = ALL_WEEKDAYS.holidays()
    assert only_holiday.holidays() is only_holiday
    assert await only_holiday.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}

    subtraction = SubtractionBDCalendar(business, (undefined,))
    assert await subtraction.get_day_type(date(2024, 1, 3)) is DayType.Undefined
    holiday_base = SubtractionBDCalendar(holiday, (business,))
    assert await holiday_base.get_day_type(d) is DayType.Holiday
    assert await subtraction.get_day_type(d) is DayType.BusinessDay
    flattened = subtraction.minus(ALL_DAYS)
    assert await flattened.get_day_type(d) is DayType.Holiday
    assert business.calendar_id in await flattened.get_dependency_ids()
    with pytest.raises(TypeError):
        SubtractionBDCalendar(cast(BDCalendar, object()), (business,))
    for normalizer in (canonical_calendars, ordered_calendars):
        with pytest.raises(TypeError):
            normalizer((cast(BDCalendar, object()),))
        with pytest.raises(ValueError):
            normalizer(())
    assert await direct_dependency_ids((business,)) == {business.calendar_id}
    with pytest.raises(DateOperationOutOfScopeException):
        await dependency_day_type(DomainFailureCalendar(CalendarID("DOMAIN2")), d)
    with pytest.raises(CalendarLogicException) as raw_failure:
        await dependency_day_type(RawFailureCalendar(CalendarID("RAW")), d)
    assert isinstance(raw_failure.value.__cause__, RuntimeError)
    assert (undefined >> business).base_fallback_calendars() == (undefined, business)

    async def invalid(d: date) -> DayType:
        return cast(DayType, "bad")

    with pytest.raises(CalendarLogicException):
        await dependency_day_type(def_functional_calendar(CalendarID("INVALID"), invalid), d)


@pytest.mark.asyncio
async def test_factories_cover_invalid_values_boundaries_and_cached_months() -> None:
    """Factories validate callbacks, dates, positions, and date-range edges."""
    for value in (-1, True, 123456789):
        with pytest.raises((TypeError, ValueError)):
            at(value)
    with pytest.raises(TypeError):
        nth_day_of_month(cast(int, "1"))
    with pytest.raises(ValueError):
        nth_day_of_month(32)
    selector = nth_day_of_month(31)
    assert await selector.get_day_type(date(2024, 2, 29)) is DayType.Holiday
    month = nth_business_day_of_month(ALL_WEEKDAYS, 1)
    assert await month.get_day_type(date(2024, 1, 1)) is DayType.BusinessDay
    assert await month.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await month.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert month.business_days() is month
    assert await range_start_days(ALL_DAYS).get_day_type(date.min) is DayType.BusinessDay
    assert await range_end_days(ALL_DAYS).get_day_type(date.max) is DayType.BusinessDay
    starts = range_start_days(ALL_WEEKDAYS)
    ends = range_end_days(ALL_WEEKDAYS)
    assert await starts.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await ends.get_day_type(date(2024, 1, 2)) is DayType.Holiday
    assert await starts.get_day_type(date(2024, 1, 6)) is DayType.Holiday
    assert await ends.get_day_type(date(2024, 1, 6)) is DayType.Holiday
    assert await starts.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert await ends.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}

    with pytest.raises(TypeError):
        def_functional_calendar(
            CalendarID("BAD"), cast(Callable[[date], DayType], 1)
        )
    with pytest.raises(TypeError):
        def_functional_calendar(
            CalendarID("BAD"),
            lambda d: DayType.BusinessDay,
            cast(Callable[[], Set[CalendarID]], 1),
        )
    no_dependencies = def_functional_calendar(
        CalendarID("NONE"), lambda d: DayType.BusinessDay
    )
    assert await no_dependencies.get_dependency_ids() == set()
    invalid_dependencies = def_functional_calendar(
        CalendarID("BAD_DEPS"),
        lambda d: DayType.BusinessDay,
        lambda: cast(Set[CalendarID], {CalendarID("")}),
    )
    with pytest.raises(CalendarLogicException):
        await invalid_dependencies.get_dependency_ids()

    def domain_classifier(d: date) -> DayType:
        raise DateOperationOutOfScopeException(d, ALL_DAYS)

    def domain_dependencies() -> Set[CalendarID]:
        raise CalendarCannotLoadException(CalendarID("DEPENDENCY"))

    callable_domain = def_functional_calendar(
        CalendarID("CALLABLE_DOMAIN"), domain_classifier, domain_dependencies
    )
    with pytest.raises(DateOperationOutOfScopeException):
        await callable_domain.get_day_type(date.today())
    with pytest.raises(CalendarCannotLoadException):
        await callable_domain.get_dependency_ids()


@pytest.mark.asyncio
async def test_primitive_and_composite_mapping_rainy_contracts() -> None:
    """Mappings cover sentinel, binding, reverse, cache, and displacement failures."""
    with pytest.raises(TypeError):
        ThisOrNextMapOperation(cast(BDCalendar, object()))
    operation = ThisOrNextMapOperation(ALL_WEEKDAYS)
    assert await operation.map_date(date(2024, 1, 7)) == date(2024, 1, 8)
    assert await operation.map_date(date(2024, 1, 7)) == date(2024, 1, 8)
    assert await operation.map_date_reverse(date(2024, 1, 8)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )
    assert await operation.get_dependency_ids() == {CalendarID("ALL_WEEKDAYS")}
    assert await ThisOrNextMapOperation(ALL_DAYS).map_date_reverse(date.min) == (
        date.min,
        date.min,
    )
    assert repr(operation.with_base_calendar(ALL_DAYS)) == ".map_this_or_next(ALL_DAYS)"
    sentinel_operation = ThisOrNextMapOperation()
    assert await sentinel_operation.get_dependency_ids() == set()
    with pytest.raises(UnappliedCalendarOperationException):
        await sentinel_operation.map_date(date.today())

    previous = ThisOrPrevMapOperation(ALL_WEEKDAYS)
    sunday = date(2024, 1, 7)
    assert await previous.map_date(sunday) == date(2024, 1, 5)
    assert await previous.map_date(sunday) == date(2024, 1, 5)
    assert repr(previous.with_base_calendar(ALL_DAYS)) == ".map_this_or_prev(ALL_DAYS)"
    far = ThisOrNextMapOperation(at(date(2024, 5, 1)))
    with pytest.raises(DateOperationOutOfScopeException):
        await far.map_date(date(2024, 1, 1))
    with pytest.raises(DateOperationOutOfScopeException):
        await far.map_date_reverse(date(2024, 1, 1))

    for value in (True, 1.5):
        with pytest.raises(TypeError):
            ShiftNDaysMapOperation(cast(int, value), ALL_DAYS)
    shift = ShiftNDaysMapOperation(1, ALL_DAYS)
    assert await shift.map_date(date(2024, 1, 1)) == date(2024, 1, 2)
    assert await shift.map_date(date(2024, 1, 1)) == date(2024, 1, 2)
    assert repr(shift.with_base_calendar(ALL_WEEKDAYS)).startswith(".shift_n_days")
    with pytest.raises(TypeError):
        BDCalendarMapping(operations=(cast(ShiftNDaysMapOperation, object()),))
    unapplied = BDCalendarMapping()
    assert await unapplied.get_dependency_ids() == set()
    with pytest.raises(UnappliedCalendarOperationException):
        await unapplied.map_date_reverse(date.today())
    with pytest.raises(UnappliedCalendarOperationException):
        await unapplied.as_calendar()
    applied = await unapplied.apply(ALL_DAYS)
    assert await applied.map_date(date.today()) == date.today()
    assert await applied.map_date_reverse(date.today()) == (date.today(), date.today())
    assert applied.map_this_or_next().map_this_or_prev().shift_n_days(0).has_applied
    result = await applied.as_calendar()
    assert result.calendar_id == CalendarID("ALL_DAYS.as_calendar()")
    with pytest.raises(ValueError):
        CalendarMapBDCalendar(CalendarID("BAD"), unapplied)
    for method in (
        SELF_CALENDAR.get_day_type(date.today()),
        SELF_CALENDAR.next_bd(date.today()),
        SELF_CALENDAR.prev_bd(date.today()),
        SELF_CALENDAR.gen_year(2024),
    ):
        with pytest.raises(UnappliedCalendarOperationException):
            await method


@pytest.mark.parametrize(
    "content",
    (
        [],
        {"business_days": []},
        {"business_days": {}, "holidays": []},
        {"business_days": [1], "holidays": []},
        {"business_days": ["20240101", "20240101"], "holidays": []},
        {"business_days": ["20240101"], "holidays": ["20240101"]},
        {"business_days": ["bad"], "holidays": []},
    ),
)
def test_strict_calendar_json_rejects_every_schema_failure(
    tmp_path: Path,
    content: object,
) -> None:
    """Strict file parsing rejects malformed structure, dates, and overlap."""
    path = tmp_path / "BAD.calendar.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        read_calendar_json(path, CalendarID("BAD"))


@pytest.mark.asyncio
async def test_filesystem_loader_path_kinds_and_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filesystem loader declines unsafe paths and propagates cancellation."""
    with pytest.raises(TypeError):
        FileSystemHardcodedBDCalendarLoader(cast(Path, "bad"))
    loader = FileSystemHardcodedBDCalendarLoader(tmp_path)
    manager = use_calendar_manager((loader,))
    assert await loader.load_calendar(CalendarID("../BAD"), manager) is None
    assert await loader.load_calendar(CalendarID("MISSING"), manager) is None
    original_resolve = Path.resolve

    def escaped_resolve(path: Path, strict: bool = False) -> Path:
        if path.name == "ESCAPE.calendar.json":
            return tmp_path.parent / "outside.calendar.json"
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", escaped_resolve)
    assert await loader.load_calendar(CalendarID("ESCAPE"), manager) is None
    monkeypatch.setattr(Path, "resolve", original_resolve)
    (tmp_path / "DIR.calendar.json").mkdir()
    with pytest.raises(CalendarCannotLoadException):
        await loader.load_calendar(CalendarID("DIR"), manager)
    path = tmp_path / "CANCEL.calendar.json"
    path.write_text('{"business_days": [], "holidays": []}', encoding="utf-8")

    async def cancel_thread(function: object, *args: object) -> object:
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "to_thread", cancel_thread)
    with pytest.raises(asyncio.CancelledError):
        await loader.load_calendar(CalendarID("CANCEL"), manager)


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


def test_remaining_total_builtin_and_weekday_validation() -> None:
    """Year-boundary builtins and weekday validation cover their complete contract."""
    assert asyncio.run(BEGIN_OF_YEARS.get_day_type(date(2024, 1, 1))) is DayType.BusinessDay
    assert asyncio.run(END_OF_YEARS.get_day_type(date(2024, 12, 31))) is DayType.BusinessDay
    with pytest.raises(ValueError):
        WeekdayBDCalendar(CalendarID("BAD"), 7)
