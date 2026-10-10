"""Canonical singleton calendar registry.

Declares ``BUILTIN_CALENDARS``.
"""

from lclang.utils.calendar.builtins.all_day_calendar import ALL_DAYS
from lclang.utils.calendar.builtins.period_boundary_calendar import (
    BEGIN_OF_MONTHS,
    BEGIN_OF_YEARS,
    END_OF_MONTHS,
    END_OF_YEARS,
)
from lclang.utils.calendar.builtins.selected_weekday_calendar import (
    FRIDAYS,
    MONDAYS,
    SATURDAYS,
    SUNDAYS,
    THURSDAYS,
    TUESDAYS,
    WEDNESDAYS,
)
from lclang.utils.calendar.builtins.weekday_calendar import ALL_WEEKDAYS
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID

# Mutable-by-contract registry whose values are canonical singleton calendars.
# Unitless registry keys come from builtin calendar IDs. Explicit entries map each supported
# spelling to its canonical singleton, avoiding dynamic discovery and duplicate instances.
BUILTIN_CALENDARS: dict[CalendarID, BDCalendar] = {
    calendar.calendar_id: calendar
    for calendar in (
        ALL_DAYS,
        ALL_WEEKDAYS,
        MONDAYS,
        TUESDAYS,
        WEDNESDAYS,
        THURSDAYS,
        FRIDAYS,
        SATURDAYS,
        SUNDAYS,
        BEGIN_OF_MONTHS,
        END_OF_MONTHS,
        BEGIN_OF_YEARS,
        END_OF_YEARS,
    )
}
