"""Reviewed LCL calendar namespace and manager construction values."""

from lclang.stdlib.namespaces import StdlibNamespace
from lclang.utils.calendar.builtins import (
    ALL_DAYS,
    ALL_WEEKDAYS,
    BEGIN_OF_MONTHS,
    BEGIN_OF_YEARS,
    END_OF_MONTHS,
    END_OF_YEARS,
    FRIDAYS,
    MONDAYS,
    SATURDAYS,
    SUNDAYS,
    THURSDAYS,
    TUESDAYS,
    WEDNESDAYS,
)
from lclang.utils.calendar.factories import (
    at,
    def_functional_calendar,
    nth_business_day_of_month,
    nth_day_of_month,
    range_end_days,
    range_start_days,
)
from lclang.utils.calendar.types import DayType

# Reviewed read-only namespace exposing calendar construction to LCL.
# Unitless namespace identity and entries below come from the reviewed calendar API. Explicit
# exports keep LCL factories and singleton bindings aligned with the supported Python calendar
# surface.
CALENDARS_NAMESPACE = StdlibNamespace(
    "calendars",
    {
        "DayType": DayType,
        "at": at,
        "nth_day_of_month": nth_day_of_month,
        "nth_business_day_of_month": nth_business_day_of_month,
        "range_start_days": range_start_days,
        "range_end_days": range_end_days,
        "def_functional_calendar": def_functional_calendar,
        "ALL_DAYS": ALL_DAYS,
        "ALL_WEEKDAYS": ALL_WEEKDAYS,
        "MONDAYS": MONDAYS,
        "TUESDAYS": TUESDAYS,
        "WEDNESDAYS": WEDNESDAYS,
        "THURSDAYS": THURSDAYS,
        "FRIDAYS": FRIDAYS,
        "SATURDAYS": SATURDAYS,
        "SUNDAYS": SUNDAYS,
        "BEGIN_OF_MONTHS": BEGIN_OF_MONTHS,
        "END_OF_MONTHS": END_OF_MONTHS,
        "BEGIN_OF_YEARS": BEGIN_OF_YEARS,
        "END_OF_YEARS": END_OF_YEARS,
    },
)
