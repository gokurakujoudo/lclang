"""Callable-backed functional calendar factory."""

from collections.abc import Awaitable, Callable, Set
from datetime import date
from typing import final

from lclang.utils.calendar.errors import CalendarLogicException
from lclang.utils.calendar.functional import FunctionalBDCalendar
from lclang.utils.calendar.helpers import CALENDAR_ERRORS, require_day_type, resolve_result
from lclang.utils.calendar.types import CalendarID, DayType

type DayTypeFunction = Callable[[date], DayType | Awaitable[DayType]]
type DependencyFunction = Callable[[], Set[CalendarID] | Awaitable[Set[CalendarID]]]


@final
class CallableBDCalendar(FunctionalBDCalendar):
    """Delegate classification and dependencies to supplied callables.

    :param calendar_id: Unique calendar identifier.
    :param day_type_function: Sync or async date classifier.
    :param dependency_function: Optional sync or async dependency provider.
    """

    __slots__ = ("day_type_function", "dependency_function")

    def __init__(
        self,
        calendar_id: CalendarID,
        day_type_function: DayTypeFunction,
        dependency_function: DependencyFunction | None,
    ) -> None:
        """Create a callable-backed calendar.

        :param calendar_id: Unique calendar identifier.
        :param day_type_function: Sync or async date classifier.
        :param dependency_function: Optional dependency provider.
        :returns: ``None``.
        :raises TypeError: If either supplied callback is not callable.
        """
        if not callable(day_type_function):
            raise TypeError("day type function must be callable")
        if dependency_function is not None and not callable(dependency_function):
            raise TypeError("dependency function must be callable")
        self.day_type_function = day_type_function
        self.dependency_function = dependency_function
        super().__init__(calendar_id)

    async def get_day_type(self, d: date) -> DayType:
        """Invoke and validate the supplied classifier.

        :param d: Date to classify.
        :returns: Validated callback result.
        :raises CalendarLogicException: If callback logic fails.
        """
        try:
            return require_day_type(await resolve_result(self.day_type_function(d)))
        except CALENDAR_ERRORS:
            raise
        except Exception as error:
            raise CalendarLogicException(self.calendar_id) from error

    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Invoke and validate the optional dependency provider.

        :returns: Immutable direct dependency set.
        :raises CalendarLogicException: If callback logic fails.
        :raises TypeError: If dependency values are not non-empty text.
        """
        if self.dependency_function is None:
            return frozenset()
        try:
            values = await resolve_result(self.dependency_function())
            if any(not isinstance(value, str) or not value for value in values):
                raise TypeError("dependency IDs must be non-empty text")
            return frozenset(CalendarID(value) for value in values)
        except CALENDAR_ERRORS:
            raise
        except Exception as error:
            raise CalendarLogicException(self.calendar_id) from error


def def_functional_calendar(
    calendar_id: CalendarID,
    get_day_type_func: DayTypeFunction,
    get_dependency_ids_func: DependencyFunction | None = None,
) -> CallableBDCalendar:
    """Create a calendar backed by supplied sync or async callables.

    :param calendar_id: Unique calendar identifier.
    :param get_day_type_func: Date classifier callable.
    :param get_dependency_ids_func: Optional dependency callable.
    :returns: Callable-backed functional calendar.
    """
    return CallableBDCalendar(calendar_id, get_day_type_func, get_dependency_ids_func)
