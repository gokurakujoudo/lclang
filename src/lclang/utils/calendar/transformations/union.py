"""Business-day union calendar."""

from collections.abc import Iterable, Set
from datetime import date
from typing import final

from lclang.error import LclUtilityError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.utilities import Code as utilities_codes
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.transformations.logic import dependency_day_type, direct_dependency_ids
from lclang.utils.calendar.transformations.operands import canonical_calendars
from lclang.utils.calendar.types import CalendarID, DayType


@guard_constructor(LclValidationError, utilities_codes.NATIVE_714)
@final
class UnionBDCalendar(FunctionalBDCalendar):
    """Combine calendars by accepting any business-day classification.

    :param base_calendars: Calendars to combine as a commutative set.
    """

    __slots__ = ("base_calendars",)

    def __init__(self, base_calendars: Iterable[BDCalendar]) -> None:
        """Create a canonical flattened union.

        :param base_calendars: Calendars to combine as a commutative set.
        :returns: ``None``.
        """
        bases = canonical_calendars(base_calendars)
        self.base_calendars = frozenset(bases)
        super().__init__(CalendarID(f"({' + '.join(map(repr, bases))})"))

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
    async def get_day_type(self, d: date) -> DayType:
        """Apply business-first union precedence.

        :param d: Date to classify.
        :returns: Union classification.
        """
        values = [
            await dependency_day_type(calendar, d) for calendar in self.base_union_calendars()
        ]
        if DayType.BusinessDay in values:
            return DayType.BusinessDay
        return DayType.Holiday if DayType.Holiday in values else DayType.Undefined

    @guard_async_failure(LclUtilityError, utilities_codes.NATIVE_714)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return direct union operand IDs.

        :returns: Immutable direct dependency set.
        """
        return await direct_dependency_ids(self.base_calendars)

    @guard_failure(LclUtilityError, utilities_codes.NATIVE_714)
    def base_union_calendars(self) -> tuple[BDCalendar, ...]:
        """Return canonical flattened union operands.

        :returns: Stable operand tuple.
        """
        return tuple(sorted(self.base_calendars, key=lambda item: item.calendar_id))
