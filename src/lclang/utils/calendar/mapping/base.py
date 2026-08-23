"""Abstract date-mapping operation and bounded reverse lookup."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from datetime import date
from types import MappingProxyType

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.constants import MAX_BUSINESS_DAY_SHIFT_DAYS
from lclang.utils.calendar.errors import DateOperationOutOfScopeException
from lclang.utils.calendar.helpers import safe_add_days
from lclang.utils.calendar.mapping.sentinel import SELF_CALENDAR
from lclang.utils.calendar.types import CalendarID


class BDCalendarMapOperation(ABC):
    """Map dates monotonically through one calendar operation.

    :param base_calendar: Calendar used by the operation.
    """

    __slots__ = ("_mapped_dates", "base_calendar", "mapped_dates")

    def __setattr__(self, name: str, value: object) -> None:
        """Set caches once while preventing configuration replacement.

        :param name: Attribute name.
        :param value: Attribute value.
        :returns: ``None``.
        :raises AttributeError: If immutable public configuration already exists.
        """
        if name in {"base_calendar", "mapped_dates", "n", "operations"}:
            try:
                object.__getattribute__(self, name)
            except AttributeError:
                pass
            else:
                raise AttributeError(f"{name} is immutable")
        object.__setattr__(self, name, value)

    def __init__(self, base_calendar: BDCalendar = SELF_CALENDAR) -> None:
        """Create an empty successful-result cache.

        :param base_calendar: Calendar used by the operation.
        :returns: ``None``.
        :raises TypeError: If *base_calendar* is not a calendar.
        """
        if not isinstance(base_calendar, BDCalendar):
            raise TypeError("mapping base must be a BDCalendar")
        self.base_calendar = base_calendar
        self._mapped_dates: dict[date, date] = {}
        self.mapped_dates: Mapping[date, date] = MappingProxyType(self._mapped_dates)

    @abstractmethod
    async def map_date(self, base_date: date) -> date:
        """Map one source date to one target date.

        :param base_date: Source date.
        :returns: Target date.
        :raises DateOperationOutOfScopeException: If no valid target exists.
        """

    @abstractmethod
    def with_base_calendar(self, calendar: BDCalendar) -> BDCalendarMapOperation:
        """Return a configuration-equivalent operation bound to a calendar.

        :param calendar: Concrete calendar to bind.
        :returns: New bound operation.
        """

    async def map_date_reverse(self, target_date: date) -> tuple[date, date]:
        """Find the inclusive source range mapped to a target date.

        :param target_date: Target date whose preimage is requested.
        :returns: First and last source dates mapped to the target.
        :raises DateOperationOutOfScopeException: If the target has no preimage.
        """
        anchor = next(
            (
                source
                for source, mapped in self._mapped_dates.items()
                if mapped == target_date
            ),
            None,
        )
        if anchor is None:
            for distance in range(MAX_BUSINESS_DAY_SHIFT_DAYS + 1):
                offsets = (0,) if distance == 0 else (-distance, distance)
                for offset in offsets:
                    candidate = safe_add_days(target_date, offset)
                    if candidate is None:
                        continue
                    try:
                        mapped = await self.map_date(candidate)
                    except DateOperationOutOfScopeException:
                        continue
                    if mapped == target_date:
                        anchor = candidate
                        break
                if anchor is not None:
                    break
        if anchor is None:
            raise DateOperationOutOfScopeException(target_date, self.base_calendar)

        lower = safe_add_days(target_date, -MAX_BUSINESS_DAY_SHIFT_DAYS) or date.min
        upper = anchor
        while lower < upper:
            middle = date.fromordinal((lower.toordinal() + upper.toordinal()) // 2)
            try:
                mapped = await self.map_date(middle)
            except DateOperationOutOfScopeException:
                lower = date.fromordinal(middle.toordinal() + 1)
                continue
            if mapped < target_date:
                lower = date.fromordinal(middle.toordinal() + 1)
            else:
                upper = middle
        first = lower

        lower = anchor
        upper = safe_add_days(target_date, MAX_BUSINESS_DAY_SHIFT_DAYS) or date.max
        while lower < upper:
            middle = date.fromordinal(
                (lower.toordinal() + upper.toordinal() + 1) // 2
            )
            try:
                mapped = await self.map_date(middle)
            except DateOperationOutOfScopeException:
                upper = date.fromordinal(middle.toordinal() - 1)
                continue
            if mapped <= target_date:
                lower = middle
            else:
                upper = date.fromordinal(middle.toordinal() - 1)
        return first, lower

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Return the operation's concrete calendar dependency.

        :returns: Empty set for the sentinel, otherwise one direct ID.
        """
        if self.base_calendar is SELF_CALENDAR:
            return frozenset()
        return frozenset((self.base_calendar.calendar_id,))

    def validate_displacement(self, source: date, target: date) -> date:
        """Reject a primitive target farther than the mapping bound.

        :param source: Source date.
        :param target: Candidate target date.
        :returns: Validated target date.
        :raises DateOperationOutOfScopeException: If displacement exceeds the bound.
        """
        if abs((target - source).days) > MAX_BUSINESS_DAY_SHIFT_DAYS:
            raise DateOperationOutOfScopeException(source, self.base_calendar)
        self._mapped_dates[source] = target
        return target
