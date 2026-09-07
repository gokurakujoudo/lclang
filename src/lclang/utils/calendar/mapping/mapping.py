"""Immutable chain of applied calendar mapping operations."""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import (
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
from lclang.utils.calendar.mapping.base import BDCalendarMapOperation
from lclang.utils.calendar.mapping.business_day_adjustment import (
    ThisOrNextMapOperation,
    ThisOrPrevMapOperation,
)
from lclang.utils.calendar.mapping.sentinel import SELF_CALENDAR
from lclang.utils.calendar.mapping.shift import ShiftNDaysMapOperation
from lclang.utils.calendar.types import CalendarID


@final
class BDCalendarMapping(BDCalendarMapOperation):
    """Apply an immutable ordered chain of mapping operations.

    :param base_calendar: Source calendar or unapplied sentinel.
    :param operations: Operations in forward application order.
    """

    __slots__ = ("operations",)

    def __init__(
        self,
        base_calendar: BDCalendar = SELF_CALENDAR,
        operations: Iterable[BDCalendarMapOperation] = (),
    ) -> None:
        """Create and bind an immutable operation chain.

        :param base_calendar: Source calendar or unapplied sentinel.
        :param operations: Operations in forward application order.
        :returns: ``None``.
        :raises TypeError: If an operation has an incompatible type.
        """
        super().__init__(base_calendar)
        values = tuple(operations)
        if any(not isinstance(item, BDCalendarMapOperation) for item in values):
            raise TypeError("mapping operations must be BDCalendarMapOperation values")
        if base_calendar is not SELF_CALENDAR:
            values = tuple(
                item.with_base_calendar(base_calendar)
                if item.base_calendar is SELF_CALENDAR
                else item
                for item in values
            )
        self.operations = values

    @property
    def has_applied(self) -> bool:
        """Return whether the mapping owns a concrete source calendar.

        :returns: Application state.
        """
        return self.base_calendar is not SELF_CALENDAR

    async def map_date(self, base_date: date) -> date:
        """Map a date through every operation.

        :param base_date: Source date.
        :returns: Final mapped date.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException()
        cached = self._mapped_dates.get(base_date)
        if cached is not None:
            return cached
        target = base_date
        for operation in self.operations:
            target = await operation.map_date(target)
        self._mapped_dates[base_date] = target
        return target

    async def map_date_reverse(self, target_date: date) -> tuple[date, date]:
        """Find the inclusive source range mapped to a target.

        :param target_date: Final target date.
        :returns: First and last source dates mapped to the target.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        :raises DateOperationOutOfScopeException: If the target has no preimage.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException()
        first = target_date
        last = target_date
        for operation in reversed(self.operations):
            source_first: date | None = None
            source_last: date | None = None
            current = first
            while True:
                try:
                    operation_first, operation_last = await operation.map_date_reverse(
                        current
                    )
                except DateOperationOutOfScopeException:
                    pass
                else:
                    if source_first is None:
                        source_first = operation_first
                    source_last = operation_last
                if current == last:
                    break
                current = date.fromordinal(current.toordinal() + 1)
            if source_first is None or source_last is None:
                raise DateOperationOutOfScopeException(target_date, self.base_calendar)
            first = source_first
            last = source_last
        return first, last

    def with_base_calendar(self, calendar: BDCalendar) -> BDCalendarMapping:
        """Return an applied copy of the complete mapping.

        :param calendar: Concrete source calendar.
        :returns: New applied mapping.
        """
        return BDCalendarMapping(calendar, self.operations)

    async def apply(self, calendar: BDCalendar) -> BDCalendarMapping:
        """Apply a source calendar without mutating this mapping.

        :param calendar: Concrete source calendar.
        :returns: New applied mapping.
        """
        return self.with_base_calendar(calendar)

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Collect direct source and operation calendar IDs.

        :returns: Immutable dependency set.
        """
        values: set[CalendarID] = set()
        if self.has_applied:
            values.add(self.base_calendar.calendar_id)
        for operation in self.operations:
            values.update(await operation.get_dependency_ids())
        return frozenset(values)

    def map_this_or_next(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a this-or-next operation.

        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ThisOrNextMapOperation(selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    def map_this_or_prev(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a this-or-previous operation.

        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ThisOrPrevMapOperation(selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    def shift_n_days(self, n: int, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a signed business-day shift.

        :param n: Signed business-day count.
        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ShiftNDaysMapOperation(n, selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    async def as_calendar(self, calendar_id: CalendarID | None = None) -> BDCalendar:
        """Expose mapped source business dates as a calendar.

        :param calendar_id: Optional explicit result identifier.
        :returns: Calendar backed by this mapping.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException()
        from lclang.utils.calendar.mapping.result_calendar import CalendarMapBDCalendar

        selected = CalendarID(f"{self!r}.as_calendar()") if calendar_id is None else calendar_id
        return CalendarMapBDCalendar(selected, self)

    def __repr__(self) -> str:
        """Return source calendar followed by operation calls.

        :returns: Stable chain representation.
        """
        return f"{self.base_calendar!r}{''.join(map(repr, self.operations))}"
