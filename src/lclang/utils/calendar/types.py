"""Public scalar types used by business-day calendars."""

from enum import Enum
from typing import NewType

CalendarID = NewType("CalendarID", str)
"""Nominal identifier used as the equality and cache key for calendars."""


class DayType(Enum):
    """Classify a date as business, holiday, or not defined."""

    # Unitless public labels follow the three-state calendar contract; a distinct
    # Undefined value preserves no-opinion semantics rather than treating it as Holiday.
    # The date is available for business-day calculations.
    BusinessDay = "BusinessDay"
    # The date is explicitly unavailable for business-day calculations.
    Holiday = "Holiday"
    # The calendar has no classification for the date.
    Undefined = "Undefined"

