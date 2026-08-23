"""Abstract business-day calendar and its construction helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Set
from datetime import date
from typing import TYPE_CHECKING

from lclang.utils.calendar.types import CalendarID, DayType

if TYPE_CHECKING:
    from lclang.utils.calendar.mapping import BDCalendarMapping
    from lclang.utils.calendar.transformations import (
        FallbackBDCalendar,
        IntersectBDCalendar,
        SubtractionBDCalendar,
        UnionBDCalendar,
    )


class BDCalendar(ABC):
    """Classify dates and navigate business days for one stable identity.

    :param calendar_id: Non-empty unique calendar identifier.
    """

    __slots__ = ("calendar_id",)

    def __init__(self, calendar_id: CalendarID) -> None:
        """Create a calendar with immutable identity.

        :param calendar_id: Non-empty unique calendar identifier.
        :returns: ``None``.
        :raises TypeError: If *calendar_id* is not text.
        :raises ValueError: If *calendar_id* is empty.
        """
        if not isinstance(calendar_id, str):
            raise TypeError("calendar ID must be text")
        if not calendar_id:
            raise ValueError("calendar ID cannot be empty")
        self.calendar_id = CalendarID(calendar_id)

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent reassignment of public configuration fields.

        :param name: Attribute name being assigned.
        :param value: Candidate new value.
        :returns: ``None``.
        :raises AttributeError: If an existing public field is reassigned.
        """
        if not name.startswith("_") and hasattr(self, name):
            raise AttributeError(f"calendar field {name!r} is immutable")
        object.__setattr__(self, name, value)

    def __hash__(self) -> int:
        """Hash the calendar by its unique identifier.

        :returns: Hash of :attr:`calendar_id`.
        """
        return hash(self.calendar_id)

    def __eq__(self, another: object) -> bool:
        """Compare calendar identities.

        :param another: Candidate calendar value.
        :returns: Whether both calendars have the same identifier.
        """
        return isinstance(another, BDCalendar) and self.calendar_id == another.calendar_id

    def __repr__(self) -> str:
        """Return the single-line calendar identifier.

        :returns: Calendar ID text.
        """
        return str(self.calendar_id)

    @abstractmethod
    async def get_day_type(self, d: date) -> DayType:
        """Classify one date.

        :param d: Date to classify.
        :returns: Day type supplied by the calendar.
        """

    @abstractmethod
    async def next_bd(self, d: date) -> date:
        """Return the first business day strictly after a date.

        :param d: Source date.
        :returns: Next business date.
        :raises DateOperationOutOfScopeException: If no date can be resolved.
        """

    @abstractmethod
    async def prev_bd(self, d: date) -> date:
        """Return the first business day strictly before a date.

        :param d: Source date.
        :returns: Previous business date.
        :raises DateOperationOutOfScopeException: If no date can be resolved.
        """

    @abstractmethod
    async def gen_year(self, year: int) -> dict[date, DayType]:
        """Generate classifications for one complete year.

        :param year: Gregorian year from 1 through 9999.
        :returns: Date-to-day-type snapshot; undefined dates may be absent.
        """

    async def this_or_next_bd(self, d: date) -> date:
        """Return *d* when business, otherwise its next business day.

        :param d: Source date.
        :returns: Source or next business date.
        """
        return d if await self.get_day_type(d) is DayType.BusinessDay else await self.next_bd(d)

    async def this_or_prev_bd(self, d: date) -> date:
        """Return *d* when business, otherwise its previous business day.

        :param d: Source date.
        :returns: Source or previous business date.
        """
        return d if await self.get_day_type(d) is DayType.BusinessDay else await self.prev_bd(d)

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct dependency calendar IDs.

        :returns: Empty immutable dependency set by default.
        """
        return frozenset()

    def union(self, another: BDCalendar) -> UnionBDCalendar:
        """Return the business-day union with another calendar.

        :param another: Calendar to combine.
        :returns: Canonical union calendar.
        """
        from lclang.utils.calendar.transformations import UnionBDCalendar

        return UnionBDCalendar((*self.base_union_calendars(), *another.base_union_calendars()))

    def base_union_calendars(self) -> tuple[BDCalendar, ...]:
        """Return calendars flattened into a surrounding union.

        :returns: This calendar as one union operand.
        """
        return (self,)

    def minus(self, another: BDCalendar) -> SubtractionBDCalendar:
        """Subtract another calendar's business days.

        :param another: Calendar whose business dates become holidays.
        :returns: Canonical subtraction calendar.
        """
        from lclang.utils.calendar.transformations import SubtractionBDCalendar

        return SubtractionBDCalendar(self, (another,))

    def intersect(self, another: BDCalendar) -> IntersectBDCalendar:
        """Return the business-day intersection with another calendar.

        :param another: Calendar to combine.
        :returns: Canonical intersection calendar.
        """
        from lclang.utils.calendar.transformations import IntersectBDCalendar

        values = (*self.base_intersect_calendars(), *another.base_intersect_calendars())
        return IntersectBDCalendar(values)

    def base_intersect_calendars(self) -> tuple[BDCalendar, ...]:
        """Return calendars flattened into a surrounding intersection.

        :returns: This calendar as one intersection operand.
        """
        return (self,)

    def revert(self) -> BDCalendar:
        """Return a calendar with business and holiday values exchanged.

        :returns: Reverted calendar.
        """
        from lclang.utils.calendar.transformations import RevertBDCalendar

        return RevertBDCalendar(self)

    def fallback(self, another: BDCalendar) -> FallbackBDCalendar:
        """Use another calendar when this one is undefined.

        :param another: Lower-priority fallback calendar.
        :returns: Ordered fallback calendar.
        """
        from lclang.utils.calendar.transformations import FallbackBDCalendar

        return FallbackBDCalendar(
            (*self.base_fallback_calendars(), *another.base_fallback_calendars())
        )

    def base_fallback_calendars(self) -> tuple[BDCalendar, ...]:
        """Return calendars flattened into a surrounding fallback.

        :returns: This calendar as one fallback operand.
        """
        return (self,)

    def business_days(self) -> BDCalendar:
        """Return only this calendar's business-day classifications.

        :returns: Sparse business-day filter.
        """
        from lclang.utils.calendar.transformations import OnlyBusinessDayBDCalendar

        return OnlyBusinessDayBDCalendar(self)

    def holidays(self) -> BDCalendar:
        """Return only this calendar's holiday classifications.

        :returns: Sparse holiday filter.
        """
        from lclang.utils.calendar.transformations import OnlyHolidayBDCalendar

        return OnlyHolidayBDCalendar(self)

    def map_this_or_next(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Build a mapping to this-or-next business days.

        :param calendar: Mapping calendar, or this source calendar when omitted.
        :returns: Applied one-operation calendar mapping.
        """
        from lclang.utils.calendar.mapping import BDCalendarMapping, ThisOrNextMapOperation

        selected = self if calendar is None else calendar
        return BDCalendarMapping(self, (ThisOrNextMapOperation(selected),))

    def map_this_or_prev(self, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Build a mapping to this-or-previous business days.

        :param calendar: Mapping calendar, or this source calendar when omitted.
        :returns: Applied one-operation calendar mapping.
        """
        from lclang.utils.calendar.mapping import BDCalendarMapping, ThisOrPrevMapOperation

        selected = self if calendar is None else calendar
        return BDCalendarMapping(self, (ThisOrPrevMapOperation(selected),))

    def shift_n_days(self, n: int, calendar: BDCalendar | None = None) -> BDCalendarMapping:
        """Build a mapping shifted by business days.

        :param n: Signed business-day count.
        :param calendar: Mapping calendar, or this source calendar when omitted.
        :returns: Applied one-operation calendar mapping.
        """
        from lclang.utils.calendar.mapping import BDCalendarMapping, ShiftNDaysMapOperation

        selected = self if calendar is None else calendar
        return BDCalendarMapping(self, (ShiftNDaysMapOperation(n, selected),))

    def __add__(self, another: BDCalendar) -> UnionBDCalendar:
        """Delegate ``+`` to :meth:`union`.

        :param another: Calendar to combine.
        :returns: Union calendar.
        """
        return self.union(another)

    def __sub__(self, another: BDCalendar) -> SubtractionBDCalendar:
        """Delegate ``-`` to :meth:`minus`.

        :param another: Calendar to subtract.
        :returns: Subtraction calendar.
        """
        return self.minus(another)

    def __and__(self, another: BDCalendar) -> IntersectBDCalendar:
        """Delegate ``&`` to :meth:`intersect`.

        :param another: Calendar to combine.
        :returns: Intersection calendar.
        """
        return self.intersect(another)

    def __invert__(self) -> BDCalendar:
        """Delegate ``~`` to :meth:`revert`.

        :returns: Reverted calendar.
        """
        return self.revert()

    def __rshift__(self, another: BDCalendar) -> FallbackBDCalendar:
        """Delegate ``>>`` to :meth:`fallback`.

        :param another: Lower-priority calendar.
        :returns: Fallback calendar.
        """
        return self.fallback(another)
