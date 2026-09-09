"""Business-day intersection calendar."""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type
from lclang.utils.calendar.transformations.operands import canonical_calendars
from lclang.utils.calendar.types import CalendarID, DayType


@final
class IntersectBDCalendar(FunctionalBDCalendar):
    """Combine defined calendars with holiday veto semantics.

    :param base_calendars: Calendars to combine as a commutative set.
    """

    __slots__ = ("base_calendars",)

    def __init__(self, base_calendars: Iterable[BDCalendar]) -> None:
        """Create a canonical flattened intersection.

        :param base_calendars: Calendars to combine as a commutative set.
        :returns: ``None``.
        """
        bases = canonical_calendars(base_calendars)
        self.base_calendars = frozenset(bases)
        super().__init__(CalendarID(f"({' & '.join(map(repr, bases))})"))

    async def get_day_type(self, d: date) -> DayType:
        """Apply undefined-aware holiday-veto intersection semantics.

        :param d: Date to classify.
        :returns: Intersection classification.
        """
        values = [
            await dependency_day_type(calendar, d)
            for calendar in self.base_intersect_calendars()
        ]
        if all(value is DayType.Undefined for value in values):
            return DayType.Undefined
        if DayType.Holiday in values:
            return DayType.Holiday
        return DayType.BusinessDay

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct intersection operand IDs.

        :returns: Immutable direct dependency set.
        """
        return frozenset(calendar.calendar_id for calendar in self.base_calendars)

    def base_intersect_calendars(self) -> tuple[BDCalendar, ...]:
        """Return canonical flattened intersection operands.

        :returns: Stable operand tuple.
        """
        return tuple(sorted(self.base_calendars, key=lambda item: item.calendar_id))
