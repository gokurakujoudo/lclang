# Business-day calendars

The calendar subsystem separates classification, navigation, composition, and
date mapping. Every date is `BusinessDay`, `Holiday`, or `Undefined`; undefined
means a calendar has no opinion, not that the date is a holiday.

## What you will learn

- how to classify and navigate dates asynchronously;
- how total and sparse calendars compose;
- how mappings adjust and shift dates;
- how strict JSON calendars load through a managed cache.

## Classify, compose, and navigate

Builtins such as `ALL_WEEKDAYS` are total. `at(...)` is sparse. Union lets an
explicit special business day add an exception to the weekday rule.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import ALL_WEEKDAYS, DayType, at, nth_day_of_month


async def main() -> None:
    special = at("20240106")
    working = ALL_WEEKDAYS + special
    saturday = date(2024, 1, 6)

    assert await ALL_WEEKDAYS.get_day_type(saturday) is DayType.Holiday
    assert await special.get_day_type(date(2024, 1, 7)) is DayType.Undefined
    assert await working.get_day_type(saturday) is DayType.BusinessDay
    assert await working.next_bd(saturday) == date(2024, 1, 8)

    month_edges = nth_day_of_month(1, -1)
    assert await month_edges.get_day_type(date(2024, 2, 1)) is DayType.BusinessDay
    assert await month_edges.get_day_type(date(2024, 2, 29)) is DayType.BusinessDay


asyncio.run(main())
```

`ALL_WEEKDAYS` classifies Saturday as a holiday, while the sparse calendar
explicitly classifies that Saturday as business and has no opinion on Sunday.
Union lets the business opinion win, and strict navigation then advances to
Monday. The signed month positions independently select February's first and
last dates, including leap day.

Use `+`, `&`, `-`, `~`, and `>>` for union, intersection, subtraction,
reversal, and ordered fallback. Named methods provide the same operations when
policy is assembled dynamically.

## Adjust and shift a report date

A mapping answers where a source date moves. This example adjusts a weekend to
Monday and then schedules execution one trading day later.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import ALL_DAYS, ALL_WEEKDAYS, DayType


async def main() -> None:
    report = ALL_DAYS.map_this_or_next(ALL_WEEKDAYS)
    execution = report.shift_n_days(1, ALL_WEEKDAYS)

    assert await report.map_date(date(2024, 1, 6)) == date(2024, 1, 8)
    assert await report.map_date_reverse(date(2024, 1, 8)) == (
        date(2024, 1, 6),
        date(2024, 1, 8),
    )
    assert await execution.map_date(date(2024, 1, 6)) == date(2024, 1, 9)

    report_days = await report.as_calendar()
    assert await report_days.get_day_type(date(2024, 1, 8)) is DayType.BusinessDay


asyncio.run(main())
```

The first operation maps Saturday to the next weekday, Monday. Reverse mapping
shows that Saturday, Sunday, and Monday all converge on that target. Chaining a
strict one-business-day shift starts from Monday and reaches Tuesday. Converting
the first mapping into a calendar therefore marks Monday as a report business
day.

## Load a named strict JSON calendar

Filesystem access is explicit: the application selects the directory and
constructs the loader. Tests keep that input inside a temporary directory.

<!-- lclang-tutorial-exec -->
```python
import asyncio
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.utils.calendar import (
    CalendarID,
    DayType,
    use_calendar_manager,
    use_file_system_hardcoded_calendar_loader,
)


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-calendar-tutorial-") as directory:
        root = Path(directory)
        (root / "MARKET.calendar.json").write_text(
            json.dumps(
                {
                    "business_days": ["20240102", "20240103"],
                    "holidays": ["20240101"],
                }
            ),
            encoding="utf-8",
        )
        loader = use_file_system_hardcoded_calendar_loader(root)
        manager = use_calendar_manager([loader])
        market = await manager.use_calendar(CalendarID("MARKET"))

        assert await market.get_day_type(date(2024, 1, 1)) is DayType.Holiday
        assert await market.get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
        assert await market.get_day_type(date(2024, 1, 4)) is DayType.Undefined
        assert manager.cached_calendars[CalendarID("MARKET")] is market


asyncio.run(main())
```

The loader maps the JSON holiday and business arrays to explicit classifications.
Because January 4 appears in neither array, the sparse calendar returns
`Undefined`. The manager stores the successfully loaded instance under
`CalendarID("MARKET")`, and the identity assertion proves later lookups can
reuse it.

The JSON object must contain exactly `business_days` and `holidays` arrays of
unique strict `YYYYMMDD` strings. Managed loads are single-flight within one
event loop. Retirement removes a cached calendar and recursive dependants.

[Previous: Workflow status](10-workflow-status.md) | [Next: Production patterns](12-production-patterns.md)
