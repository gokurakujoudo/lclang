"""Callable-backed functional calendar factory.

Defines ``CallableBDCalendar``, ``def_functional_calendar``.
"""

from collections.abc import Awaitable, Callable, Set
from datetime import date
from typing import final

from lclang.error import LclError, LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import CalendarLogicException, wrap_calendar_failure
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.calendar_date_operation import (
    CALENDAR_ERRORS,
    require_day_type,
    resolve_result,
)
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.functional_calendar import FunctionalBDCalendar

type DayTypeFunction = Callable[[date], DayType | Awaitable[DayType]]
type DependencyFunction = Callable[[], Set[CalendarID] | Awaitable[Set[CalendarID]]]


@guard_constructor(LclValidationError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
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
        :raises LclValidationError: If either supplied callback is not callable.
        """
        if not callable(day_type_function):
            raise LclValidationError(
                "day type function must be callable",
                code=UtilityErrorCode.E15_DAY_TYPE_FUNCTION_MUST_BE_CALLABLE,
            )
        if dependency_function is not None and not callable(dependency_function):
            raise LclValidationError(
                "dependency function must be callable",
                code=UtilityErrorCode.E15_DEPENDENCY_FUNCTION_MUST_BE_CALLABLE,
            )
        self.day_type_function = day_type_function
        self.dependency_function = dependency_function
        super().__init__(calendar_id)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
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
            failure = wrap_calendar_failure(
                error,
                CalendarLogicException(
                    self.calendar_id,
                    code=(
                        error.code
                        if isinstance(error, LclError)
                        else UtilityErrorCode.E15_CALENDAR_CALLBACK_FAILURE
                    ),
                ),
            )
            raise failure from failure.__cause__

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
    async def get_dependency_ids(self) -> Set[CalendarID]:
        """Invoke and validate the optional dependency provider.

        :returns: Immutable direct dependency set.
        :raises CalendarLogicException: If callback logic fails.
        :raises LclValidationError: If dependency values are not non-empty text.
        """
        if self.dependency_function is None:
            return frozenset()
        try:
            values = await resolve_result(self.dependency_function())
            if any(not isinstance(value, str) or not value for value in values):
                raise LclValidationError(
                    "dependency IDs must be non-empty text",
                    code=UtilityErrorCode.E15_DEPENDENCY_IDS_MUST_BE_NON_EMPTY_TEXT,
                )
            return frozenset(CalendarID(value) for value in values)
        except CALENDAR_ERRORS:
            raise
        except Exception as error:
            failure = wrap_calendar_failure(
                error,
                CalendarLogicException(
                    self.calendar_id,
                    code=(
                        error.code
                        if isinstance(error, LclError)
                        else UtilityErrorCode.E15_CALENDAR_CALLBACK_FAILURE
                    ),
                ),
            )
            raise failure from failure.__cause__


@guard_failure(LclUtilityError, UtilityErrorCode.E15_CALENDAR_CONSTRUCTION_NATIVE_FAILURE)
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
