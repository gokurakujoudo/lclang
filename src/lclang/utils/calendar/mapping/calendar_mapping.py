"""Immutable chain of applied calendar mapping operations.

Defines ``BDCalendarMapping``.
"""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import (
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID
from lclang.utils.calendar.mapping.business_day_adjustment import (
    ThisOrNextMapOperation,
    ThisOrPrevMapOperation,
)
from lclang.utils.calendar.mapping.business_day_shift import ShiftNDaysMapOperation
from lclang.utils.calendar.mapping.date_map_operation import BDCalendarMapOperation
from lclang.utils.calendar.mapping.source_calendar_marker import SELF_CALENDAR


@guard_constructor(LclValidationError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
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
        :raises LclValidationError: If an operation has an incompatible type.
        """
        super().__init__(base_calendar)
        values = tuple(operations)
        if any(not isinstance(item, BDCalendarMapOperation) for item in values):
            raise LclValidationError(
                "mapping operations must be BDCalendarMapOperation values",
                code=UtilityErrorCode.E13_MAPPING_OPERATIONS_MUST_BE_BDCALENDARMAPOPERATION_VALUES,
            )
        if base_calendar is not SELF_CALENDAR:
            values = tuple(
                (
                    item.with_base_calendar(base_calendar)
                    if item.base_calendar is SELF_CALENDAR
                    else item
                )
                for item in values
            )
        self.operations = values

    @property
    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def has_applied(self) -> bool:
        """Return whether the mapping owns a concrete source calendar.

        :returns: Application state.
        """
        return self.base_calendar is not SELF_CALENDAR

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def map_date(self, base_date: date) -> date:
        """Map a date through every operation.

        :param base_date: Source date.
        :returns: Final mapped date.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException(
                code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
            )
        cached = self._mapped_dates.get(base_date)
        if cached is not None:
            return cached
        target = base_date
        for operation in self.operations:
            target = await operation.map_date(target)
        self._mapped_dates[base_date] = target
        return target

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def map_date_reverse(self, target_date: date) -> tuple[date, date]:
        """Find the inclusive source range mapped to a target.

        :param target_date: Final target date.
        :returns: First and last source dates mapped to the target.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        :raises DateOperationOutOfScopeException: If the target has no preimage.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException(
                code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
            )
        first = target_date
        last = target_date
        for operation in reversed(self.operations):
            source_first: date | None = None
            source_last: date | None = None
            current = first
            while True:
                try:
                    operation_first, operation_last = await operation.map_date_reverse(current)
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
                raise DateOperationOutOfScopeException(
                    target_date,
                    self.base_calendar,
                    code=UtilityErrorCode.E13_TARGET_DATE_OUT_OF_SCOPE,
                )
            first = source_first
            last = source_last
        return first, last

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def with_base_calendar(self, calendar: BDCalendar) -> BDCalendarMapping:
        """Return an applied copy of the complete mapping.

        :param calendar: Concrete source calendar.
        :returns: New applied mapping.
        """
        return BDCalendarMapping(calendar, self.operations)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def apply(self, calendar: BDCalendar) -> BDCalendarMapping:
        """Apply a source calendar without mutating this mapping.

        :param calendar: Concrete source calendar.
        :returns: New applied mapping.
        """
        return self.with_base_calendar(calendar)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
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

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def map_this_or_next(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a this-or-next operation.

        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ThisOrNextMapOperation(selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def map_this_or_prev(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a this-or-previous operation.

        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ThisOrPrevMapOperation(selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    @guard_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    def shift_n_days(self, n: int, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Append a signed business-day shift.

        :param n: Signed business-day count.
        :param calendar: Mapping calendar, or source calendar when omitted.
        :returns: New mapping chain.
        """
        selected = SELF_CALENDAR if calendar is None else calendar
        operation = ShiftNDaysMapOperation(n, selected)
        return BDCalendarMapping(self.base_calendar, (*self.operations, operation))

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E13_CALENDAR_MAPPING_NATIVE_FAILURE)
    async def as_calendar(self, calendar_id: CalendarID | None = None) -> BDCalendar:
        """Expose mapped source business dates as a calendar.

        :param calendar_id: Optional explicit result identifier.
        :returns: Calendar backed by this mapping.
        :raises UnappliedCalendarOperationException: If no source calendar is applied.
        """
        if not self.has_applied:
            raise UnappliedCalendarOperationException(
                code=UtilityErrorCode.E13_OPERATION_IS_UNAVAILABLE
            )
        from lclang.utils.calendar.mapping.mapped_date_calendar import CalendarMapBDCalendar

        selected = CalendarID(f"{self!r}.as_calendar()") if calendar_id is None else calendar_id
        return CalendarMapBDCalendar(selected, self)

    def __repr__(self) -> str:
        """Return source calendar followed by operation calls.

        :returns: Stable chain representation.
        """
        return f"{self.base_calendar!r}{''.join(map(repr, self.operations))}"
