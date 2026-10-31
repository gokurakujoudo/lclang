# Business-day calendars

The calendar subsystem separates classification, navigation, composition, and
date mapping. Every date is `BusinessDay`, `Holiday`, or `Undefined`; undefined
means a calendar has no opinion, not that the date is a holiday.

## What you will learn

- how to classify and navigate dates asynchronously;
- how total and sparse calendars compose;
- how mappings adjust and shift dates;
- how strict JSON calendars load through a managed cache;
- how CLI configuration and database-backed calendars supply date rules.

## Classify, compose, and navigate

Builtins such as `ALL_WEEKDAYS` are total. `at(...)` is sparse. Union lets an
explicit special business day add an exception to the weekday rule.

<!-- lclang-doc-exec -->
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

<!-- lclang-doc-exec -->
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

<!-- lclang-doc-exec -->
```python
import asyncio
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.utils.calendar import CalendarID, DayType, use_calendar_manager, use_file_system_hardcoded_calendar_loader


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

## Load a JSON calendar from CLI configuration

Put the following files beside the Python program. The calendar ID `MARKET`
selects `calendars/MARKET.calendar.json` under the loader directory.

<!-- lclang-doc-case: cli-json-calendar -->

`calendars/MARKET.calendar.json`:

<!-- lclang-doc-file: calendars/MARKET.calendar.json -->
```json
{
  "business_days": ["20240218"],
  "holidays": ["20240101"]
}
```

`calendar.lclcfg`:

<!-- lclang-doc-file: calendar.lclcfg -->
```lclcfg
calendar_dir: f"{__dir__}/calendars"
calendar_loader: use_file_system_hardcoded_calendar_loader(calendar_dir)
calendar_manager: use_calendar_manager([calendar_loader])
market: calendar_manager.use_calendar("MARKET")
market_with_weekdays: market.fallback(calendars.ALL_WEEKDAYS)
```

Run this program beside the configuration file:

<!-- lclang-doc-exec -->
```python
import asyncio
import io
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, cli
from lclang.utils.calendar import DayType


@cli.command()
async def classify_command(context: CliContext) -> CliResult:
    """Classify the invocation date using the configured calendar."""
    market = await context.frame.get("market")
    weekdays = await context.frame.get("market_with_weekdays")
    classification = await market.get_day_type(context.as_of_date)
    assert classification is DayType.Holiday
    assert await market.get_day_type(date(2024, 1, 2)) is DayType.Undefined
    assert await weekdays.get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
    return CliResult.success(f"{context.as_of_date}: {classification.name}")


async def main() -> None:
    application = CliEntrance(
        CommandGroup("root", "Calendar tools", [classify_command]),
        version="1.0.0",
    )
    output = io.StringIO()
    with redirect_stdout(output):
        status = await application.run(
            [
                "python", "calendar_app.py", "classify",
                "--config", str(Path.cwd() / "calendar.lclcfg"),
                "--as-of", "20240101",
            ]
        )
    assert status == 0, output.getvalue()
    assert output.getvalue() == "2024-01-01: Holiday\n"
    print(output.getvalue(), end="")


asyncio.run(main())
```

The program prints:

<!-- lclang-doc-output: stdout -->
```text
2024-01-01: Holiday
```
<!-- /lclang-doc-case -->

The JSON object requires exactly `business_days` and `holidays` arrays of
unique, nonoverlapping `YYYYMMDD` strings. `__dir__` resolves the loader path
from the configuration file. The Frame automatically awaits the asynchronous
`use_calendar` call when `market` is requested. January 1 is a holiday in the
file; January 2 is absent and therefore `Undefined`. The optional
`market_with_weekdays` binding falls back to `calendars.ALL_WEEKDAYS` only for
undefined dates, so January 2 becomes a business day while explicit holidays
and exceptional working days retain their classifications.

## Load database overrides one year at a time

A `YearBatchBDCalendar` can query a holiday table when a date from a new year is
first requested. This in-memory SQLite example includes a holiday, an exceptional
Sunday working day, and a holiday in the following year.

<!-- lclang-doc-exec -->
```python
import asyncio
import sqlite3
from contextlib import closing
from datetime import date

from lclang.utils.calendar import ALL_WEEKDAYS, CalendarID, DayType, YearBatchBDCalendar


class DatabaseCalendar(YearBatchBDCalendar):
    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(CalendarID("DB_HOLIDAYS"))
        self.connection = connection

    async def gen_year(self, year: int) -> dict[date, DayType]:
        rows = self.connection.execute(
            """
            SELECT day, is_business_day FROM holidays
            WHERE day >= ? AND day <= ?
            """,
            (date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()),
        )
        return {
            date.fromisoformat(day): (
                DayType.BusinessDay if is_business_day else DayType.Holiday
            )
            for day, is_business_day in rows
        }


async def main() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute(
            """
            CREATE TABLE holidays (
                day TEXT PRIMARY KEY,
                is_business_day INTEGER NOT NULL CHECK (is_business_day IN (0, 1))
            )
            """
        )
        connection.executemany(
            "INSERT INTO holidays (day, is_business_day) VALUES (?, ?)",
            [("2024-01-01", 0), ("2024-02-18", 1), ("2025-01-01", 0)],
        )
        overrides = DatabaseCalendar(connection)
        calendar = overrides.fallback(ALL_WEEKDAYS)

        assert await calendar.get_day_type(date(2024, 1, 1)) is DayType.Holiday
        assert await calendar.get_day_type(date(2024, 2, 18)) is DayType.BusinessDay
        assert await calendar.get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
        assert set(overrides.loaded_year_batches) == {2024}
        assert await calendar.get_day_type(date(2025, 1, 1)) is DayType.Holiday
        assert set(overrides.loaded_year_batches) == {2024, 2025}

        connection.execute("UPDATE holidays SET is_business_day = 1 WHERE day = '2024-01-01'")
        assert await calendar.get_day_type(date(2024, 1, 1)) is DayType.Holiday
        assert (await overrides.gen_year(2024))[date(2024, 1, 1)] is DayType.BusinessDay
        fresh = DatabaseCalendar(connection).fallback(ALL_WEEKDAYS)
        assert await fresh.get_day_type(date(2024, 1, 1)) is DayType.BusinessDay


asyncio.run(main())
```

The first request loads 2024, and the 2025 request loads a second batch. An
absent date falls through to the weekday calendar; the explicit Sunday working
day takes precedence. Loaded years are snapshots: the existing calendar retains
its first result after the database update. A direct `gen_year` call bypasses
the base class cache, and a new calendar loads the updated row. SQLite calls
here are synchronous and block the event loop; use an appropriate asynchronous
database client for slower database access. Keep the connection open for the
calendar's use and close it afterward.

[Previous: Workflow status](10-workflow-status.md) | [Next: Production patterns](12-production-patterns.md) | [Return to the series introduction](README.md)
