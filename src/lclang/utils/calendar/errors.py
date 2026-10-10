"""Compatibility exports for structured failure support."""

from lclang.error.calendar import (
    CalendarCannotLoadException,
    CalendarLogicException,
    DateOperationOutOfScopeException,
    UnappliedCalendarOperationException,
)

# Unitless names retain the established module surface.
__all__ = [
    "DateOperationOutOfScopeException",
    "CalendarCannotLoadException",
    "CalendarLogicException",
    "UnappliedCalendarOperationException",
]
