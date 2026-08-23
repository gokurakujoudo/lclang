"""Canonical singleton calendar registry."""

from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.builtins.all_days import ALL_DAYS
from lclang.utils.calendar.builtins.all_weekdays import ALL_WEEKDAYS
from lclang.utils.calendar.builtins.begin_month import BEGIN_OF_MONTHS
from lclang.utils.calendar.builtins.begin_year import BEGIN_OF_YEARS
from lclang.utils.calendar.builtins.end_month import END_OF_MONTHS
from lclang.utils.calendar.builtins.end_year import END_OF_YEARS
from lclang.utils.calendar.builtins.weekday import (
    FRIDAYS,
    MONDAYS,
    SATURDAYS,
    SUNDAYS,
    THURSDAYS,
    TUESDAYS,
    WEDNESDAYS,
)
from lclang.utils.calendar.types import CalendarID

# Mutable-by-contract registry whose values are canonical singleton calendars.
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

