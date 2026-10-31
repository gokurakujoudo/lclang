# Business-day calendars

A business calendar answers questions such as whether a settlement can run on
Tuesday, when the next processing day falls, and which dates a year's plan
contains. The same calendar provides all three operations. Its implementation
can start from whichever fact the application knows how to calculate or load.

Install `lclang` in Python 3.14 or newer as shown in the [quick start](../quick-start.md).

This chapter first uses a calendar, then builds one from a date classifier, an
ordered sequence, and yearly data. The final sections show composition, date
mapping, and loading calendars from JSON and CLI configuration. Python examples
use `datetime.date`, and calendar operations are asynchronous.

## Ask a calendar three questions

A `DayType` is `BusinessDay`, `Holiday`, or `Undefined`. `Undefined` means the
calendar has no classification for that date. Your application must decide
whether to supply a fallback or reject an unknown date; it is not evidence that
the date is a holiday.

<!-- lclang-doc-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import ALL_WEEKDAYS, DayType


async def main() -> None:
    friday = date(2024, 1, 5)
    saturday = date(2024, 1, 6)
    monday = date(2024, 1, 8)

    assert await ALL_WEEKDAYS.get_day_type(saturday) is DayType.Holiday
    assert await ALL_WEEKDAYS.next_bd(friday) == monday
    assert await ALL_WEEKDAYS.prev_bd(monday) == friday
    assert await ALL_WEEKDAYS.this_or_next_bd(friday) == friday
    assert await ALL_WEEKDAYS.this_or_next_bd(saturday) == monday

    year = await ALL_WEEKDAYS.gen_year(2024)
    assert len(year) == 366
    assert year[saturday] is DayType.Holiday
    assert year[monday] is DayType.BusinessDay


asyncio.run(main())
```

`get_day_type` answers the question for one date. `next_bd` and `prev_bd` are
strict: even when the input is a business day, they move past it. Use
`this_or_next_bd` or `this_or_prev_bd` to keep a business-day input. In this
example Friday's next business day is Monday, while the inclusive operation
keeps Friday. `gen_year` returns a date-to-`DayType` dictionary. Some calendars
return a sparse dictionary and omit undefined dates; absence is not a holiday.
The complete `ALL_WEEKDAYS` year contains all 366 dates of leap year 2024.

Date navigation looks for `BusinessDay`; `Undefined` does not stop the search.
If unknown dates must stop a business operation, check each candidate during
navigation. The [publication-aware example](#stop-when-a-year-has-not-been-published)
below implements that policy; checking only the starting date is insufficient. Functional and year-batch searches have a 1,000 calendar-day
limit; out-of-range dates or an exhausted search raise
`DateOperationOutOfScopeException`. See the
[calendar reference](../reference/calendar.md) for contracts and errors.

## Choose how to supply your calendar

Each strategy implements the same calendar interface, but derives the other
operations from a different source of information:

| Your source of truth | Supply | The base implementation provides | Good fit |
| --- | --- | --- | --- |
| A rule for one date | A classifier to `def_functional_calendar`, or `FunctionalBDCalendar.get_day_type` | Bounded forward/backward search and year generation by classifying dates | A weekday rule or date-specific service |
| An ordered series beginning at a known date | `first_bd` and `ForwardStepBDCalendar.next_bd` | Classification, previous-date lookup, and sparse year generation from the discovered sequence | A recurrence where one event yields the next |
| A whole year's data | `YearBatchBDCalendar.gen_year` | Cached year lookup and bounded forward/backward search | A holiday table or annual publication |

Choose an existing builtin or composition when it already expresses the policy.
The following examples show what an application must implement when it does not.
Every `CalendarID` identifies a policy: equality, composition and manager
caches use the ID, so give calendars with different rules distinct IDs.

## Classify one date with a function

Suppose a branch processes orders on weekdays except its monthly maintenance
day, the third Wednesday. The rule can decide each date without loading a table.
`def_functional_calendar` accepts a synchronous or asynchronous callable that
returns a `DayType`.

<!-- lclang-doc-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import CalendarID, DayType, def_functional_calendar


def classify_branch_day(day: date) -> DayType:
    if day.weekday() >= 5:
        return DayType.Holiday
    if day.weekday() == 2 and 15 <= day.day <= 21:
        return DayType.Holiday
    return DayType.BusinessDay


async def main() -> None:
    branch = def_functional_calendar(CalendarID("BRANCH_MAINTENANCE"), classify_branch_day)
    maintenance = date(2024, 2, 21)

    assert await branch.get_day_type(maintenance) is DayType.Holiday
    assert await branch.next_bd(date(2024, 2, 20)) == date(2024, 2, 22)
    assert await branch.prev_bd(date(2024, 2, 22)) == date(2024, 2, 20)
    year = await branch.gen_year(2024)
    assert len(year) == 366
    assert year[maintenance] is DayType.Holiday
    assert year[date(2024, 2, 22)] is DayType.BusinessDay


asyncio.run(main())
```

February 21 is the third Wednesday, so the search skips it. Generating the year checks every date, including weekends and leap day, and
calls the rule for dates that traversal has not already cached. A classifier may
also return `Undefined` for dates outside its policy and then use an ordered
fallback, as the database example below does.

For a stateful implementation, subclass `FunctionalBDCalendar` and implement
`async get_day_type(d)`. The base search and `gen_year` use
`cached_day_type(d)` and keep the resulting per-date snapshots in
`defined_dates`. A direct `get_day_type(d)` call invokes the classifier; it does
not itself use that base cache. Keep the rule's inputs stable for the calendar's
lifetime or replace the calendar when they change. A year request can mean 365
or 366 classifier calls, so prefer a batch source when per-date I/O is expensive.

## Generate a sequence one date at a time

A payout schedule may define business days as the 15th of every month in a
fixed year. If the next event is easier to calculate from the previous event
than to classify each day, subclass `ForwardStepBDCalendar`. Give it the first
event and implement `next_bd`. The base calls your method with the previous
generated date and caches a strictly increasing sequence.

<!-- lclang-doc-exec -->
```python
import asyncio
from datetime import date

from lclang.error import DateOperationOutOfScopeException
from lclang.utils.calendar import CalendarID, DayType, ForwardStepBDCalendar


class PayoutCalendar(ForwardStepBDCalendar):
    async def next_bd(self, day: date) -> date:
        # Also support arbitrary input dates, not only generated payout dates.
        if day < self.first_bd:
            return self.first_bd
        if day >= date(2024, 12, 15):
            raise DateOperationOutOfScopeException(day, self)
        if day.day < 15:
            return date(day.year, day.month, 15)
        return date(day.year, day.month + 1, 15)


async def main() -> None:
    payouts = PayoutCalendar(CalendarID("PAYOUTS_2024"), date(2024, 1, 15))

    assert await payouts.next_bd(date(2024, 2, 10)) == date(2024, 2, 15)
    assert await payouts.next_bd(date(2024, 2, 15)) == date(2024, 3, 15)
    assert await payouts.get_day_type(date(2024, 2, 15)) is DayType.BusinessDay
    assert await payouts.get_day_type(date(2024, 2, 16)) is DayType.Undefined
    assert await payouts.get_day_type(date(2024, 1, 14)) is DayType.Undefined
    assert await payouts.prev_bd(date(2024, 2, 16)) == date(2024, 2, 15)

    year = await payouts.gen_year(2024)
    assert len(year) == 12
    assert year[date(2024, 12, 15)] is DayType.BusinessDay
    assert date(2024, 12, 16) not in year
    assert payouts.fully_cached
    try:
        await payouts.next_bd(date(2024, 12, 15))
    except DateOperationOutOfScopeException:
        pass
    else:
        raise AssertionError("the 2024 schedule has ended")


asyncio.run(main())
```

The subclass's `next_bd` handles arbitrary input as well as previously
generated dates. This extra work matters because callers can invoke `next_bd`
directly, and `this_or_next_bd` calls it for a non-business input. The base
class calls the method with a previously generated date when extending its
cache; it does not wrap the override to find the next cached event for arbitrary
inputs. Return a strictly later `date`, and raise
`DateOperationOutOfScopeException` when a finite sequence ends. During cache
extension, a non-increasing result is a `CalendarLogicException` and exhaustion
marks the sequence complete.

Classification and previous-date lookup extend the cache from `first_bd` as
needed; `gen_year` discovers the year's events and may extend beyond year end.
The returned year is sparse: only payout dates are business days, and all other
dates, including those before `first_bd`, are `Undefined`. The example checks
that no event follows December 15. A direct call to the subclass's `next_bd`
does not populate the base cache. Reaching a distant date requires discovering
the intermediate events, so this strategy fits an ordered, reasonably bounded
sequence. Do not add a weekday fallback to a payout schedule unless ordinary
weekdays should themselves become payout days.

## Load a whole year on demand

When a database or annual publication supplies classifications in batches,
implement `YearBatchBDCalendar.gen_year(year)` and return a dictionary whose
date keys belong to that year. The database example [below](#load-database-overrides-one-year-at-a-time)
uses sparse holiday and exceptional-working-day rows, then falls back to
`ALL_WEEKDAYS` for dates absent from the table. Its first lookup loads that year;
lookup in another year loads another batch. `loaded_year(year)` is the explicit
cached lookup, while a direct call to your `gen_year(year)` runs your generator
again. The cached batch is a detached snapshot, so create a new calendar when
source data changes. `loaded_year` validates that the generator returns a
dictionary with dates from the requested year and `DayType` values; it removes
`Undefined` entries. Direct `gen_year` calls bypass that validation and cache.
The example also demonstrates this refresh.

Both functional and year-batch navigation search individual dates until a
business day is found, within the 1,000-day bound. Sparse data alone can leave
long gaps; choose a fallback that represents the business rule before searching.
The optional fallback is policy, not a claim that every unspecified date is a
weekday business day.

## Classify, compose, and navigate

Calendar operators encode different policies. In the table `B` means
`BusinessDay`, `H` means `Holiday`, and `U` means `Undefined`. The first column
is the left operand and the second is the right operand.

| Left | Right | `union` (`+`) | `intersect` (`&`) | `minus` (`-`) | `fallback` (`>>`) |
| --- | --- | --- | --- | --- | --- |
| B | B | B | B | H | B |
| B | H | B | H | B | B |
| B | U | B | B | B | B |
| H | B | B | H | H | H |
| H | H | H | H | H | H |
| H | U | H | H | H | H |
| U | B | B | B | U | B |
| U | H | H | H | U | H |
| U | U | U | U | U | U |

`union` lets business win. `intersect` lets a holiday veto, while an undefined
operand has no opinion. `minus` turns a left business day into a holiday when
the right side says business; it keeps an undefined left side undefined.
`fallback` uses the right side only when the left is undefined, so its order
matters. In particular, `B & U` is `B`: if joint operation requires both
parties to confirm every date, validate both calendars' coverage for each
candidate before accepting the intersection. `revert` (`~`) swaps B and H and leaves U unchanged. The named methods
and their operators are equivalent. `business_days()` and `holidays()` filter
out the other defined classification, leaving it undefined.

For example, putting a holiday override on the left of `+` cannot close a
weekday: union still chooses business. Ordered fallback gives the override
priority, including an exceptional Sunday working day.

<!-- lclang-doc-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import ALL_WEEKDAYS, CalendarID, DayType, HardcodedBDCalendar


async def main() -> None:
    new_year = date(2024, 1, 1)
    extra_sunday = date(2024, 2, 18)
    normal_tuesday = date(2024, 1, 2)
    overrides = HardcodedBDCalendar(
        CalendarID("MARKET_OVERRIDES"),
        {new_year: DayType.Holiday, extra_sunday: DayType.BusinessDay},
    )
    market = overrides.fallback(ALL_WEEKDAYS)

    assert await (overrides + ALL_WEEKDAYS).get_day_type(new_year) is DayType.BusinessDay
    assert await market.get_day_type(new_year) is DayType.Holiday
    assert await market.get_day_type(extra_sunday) is DayType.BusinessDay
    assert await market.get_day_type(normal_tuesday) is DayType.BusinessDay
    assert await (overrides & ALL_WEEKDAYS).get_day_type(extra_sunday) is DayType.Holiday
    assert await (~overrides).get_day_type(normal_tuesday) is DayType.Undefined


asyncio.run(main())
```

The fallback preserves both explicit exceptions and delegates the ordinary
Tuesday to the weekday rule. Intersection closes the exceptional Sunday because
`ALL_WEEKDAYS` calls it a holiday. Reversal cannot fill an undefined Tuesday.
For authoritative holiday data, use a coverage rule as well: fallback alone
cannot distinguish a published year with no exceptions from an unpublished year.


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

The first operation maps Saturday to the next weekday, Monday. The reverse
result is an inclusive pair of endpoints, so Saturday, Sunday, and Monday all
map to that target. A target with no source range raises
`DateOperationOutOfScopeException`. Each mapping primitive moves at most 100
calendar days; the [reference](../reference/calendar.md#date-mappings)
describes the limits. Chaining a strict one-business-day shift starts from Monday and reaches Tuesday. Converting
the first mapping into a calendar marks a target business when at least one
source business date maps to it; other targets are holidays. Since `ALL_DAYS`
marks all source dates business, Monday is a report business day.

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

Save this application as `calendar_app.py` beside the configuration file:

<!-- lclang-doc-file: calendar_app.py -->
```python
import asyncio

from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, cli


@cli.command()
async def classify_command(context: CliContext) -> CliResult:
    """Classify the invocation date using the configured calendar."""
    market = await context.frame.get("market")
    weekdays = await context.frame.get("market_with_weekdays")
    classification = await market.get_day_type(context.as_of_date)
    with_fallback = await weekdays.get_day_type(context.as_of_date)
    return CliResult.success(
        f"{context.as_of_date}: {classification.name} -> {with_fallback.name}"
    )


application = CliEntrance(
    CommandGroup("root", "Calendar tools", [classify_command]),
    version="1.0.0",
)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(application.run()))
```

The entry point reads the process arguments and returns the command status to
the shell. For example, run:

```console
python calendar_app.py classify --config calendar.lclcfg --as-of 20240218
```

To verify the holiday, exceptional working day, and an absent date, run this
separate program beside the same files:

<!-- lclang-doc-exec -->
```python
import subprocess
import sys
from pathlib import Path


config = str(Path.cwd() / "calendar.lclcfg")
cases = (
    ("20240101", "2024-01-01: Holiday -> Holiday\n"),
    ("20240218", "2024-02-18: BusinessDay -> BusinessDay\n"),
    ("20240102", "2024-01-02: Undefined -> BusinessDay\n"),
)
for as_of, expected in cases:
    result = subprocess.run(
        [
            sys.executable, "calendar_app.py", "classify",
            "--config", config, "--as-of", as_of,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    print(result.stdout, end="")
```

The verification program prints the original classification followed by the
classification with the weekday fallback:

<!-- lclang-doc-output: stdout -->
```text
2024-01-01: Holiday -> Holiday
2024-02-18: BusinessDay -> BusinessDay
2024-01-02: Undefined -> BusinessDay
```
<!-- /lclang-doc-case -->

The JSON object requires exactly `business_days` and `holidays` arrays of
unique, nonoverlapping `YYYYMMDD` strings. `__dir__` resolves the loader path
from the configuration file. The loader and manager functions and the
`calendars` namespace are available in the standard LCL builtins; they do not
need Python imports inside the configuration. The Frame automatically awaits
the asynchronous `use_calendar` call when `market` is requested. January 1 is
a holiday and February 18 is a business day in the file. January 2 is absent
and therefore `Undefined`. The optional
`market_with_weekdays` binding falls back to `calendars.ALL_WEEKDAYS` only for
undefined dates, so January 2 becomes a business day while explicit holidays
and exceptional working days retain their classifications.

## Load database overrides one year at a time

A `YearBatchBDCalendar` can query a holiday table when a date from a new year is
first requested. This in-memory SQLite example includes a holiday, an exceptional
Sunday working day, and a holiday in the following year. Its simple weekday
fallback assumes every requested year is covered. If publication can lag, use
the [publication-aware policy](#stop-when-a-year-has-not-been-published) below.

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

## Stop when a year has not been published

A sparse table of exceptions cannot by itself distinguish an empty published
year from a year whose rules have not arrived. Falling back to weekdays for
both would silently invent a policy for the unpublished year. Store publication
status separately, and apply the fallback only inside published years. The
following example uses SQLite to make that distinction. It also searches one
candidate at a time and stops at the first undefined date.

<!-- lclang-doc-exec -->
```python
import asyncio
import sqlite3
from contextlib import closing
from datetime import date, timedelta

from lclang.utils.calendar import (
    ALL_WEEKDAYS,
    BDCalendar,
    CalendarID,
    DayType,
    YearBatchBDCalendar,
    def_functional_calendar,
)


class ExceptionsByYear(YearBatchBDCalendar):
    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(CalendarID("PUBLISHED_EXCEPTIONS"))
        self.connection = connection

    async def gen_year(self, year: int) -> dict[date, DayType]:
        rows = self.connection.execute(
            "SELECT day, is_business_day FROM exceptions WHERE day >= ? AND day <= ?",
            (date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()),
        )
        return {
            date.fromisoformat(day): (
                DayType.BusinessDay if is_business_day else DayType.Holiday
            )
            for day, is_business_day in rows
        }


async def next_known_business(calendar: BDCalendar, day: date) -> date:
    """Search strictly forward, rejecting unknown dates and exhausted bounds."""
    for _ in range(1000):
        if day == date.max:
            raise LookupError("date range exhausted")
        day += timedelta(days=1)
        result = await calendar.get_day_type(day)
        if result is DayType.Undefined:
            raise LookupError(f"calendar not published for {day}")
        if result is DayType.BusinessDay:
            return day
    raise LookupError("no business day in 1000 days")


async def main() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE published_years (year INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE exceptions (day TEXT PRIMARY KEY, "
            "is_business_day INTEGER NOT NULL CHECK (is_business_day IN (0, 1)))"
        )
        connection.executemany("INSERT INTO published_years VALUES (?)", [(2023,), (2024,)])
        connection.executemany(
            "INSERT INTO exceptions VALUES (?, ?)",
            [("2024-01-01", 0), ("2024-02-18", 1)],
        )
        published = frozenset(row[0] for row in connection.execute("SELECT year FROM published_years"))
        overrides = ExceptionsByYear(connection)
        within_published = overrides.fallback(ALL_WEEKDAYS)

        async def classify(day: date) -> DayType:
            if day.year not in published:
                return DayType.Undefined
            return await within_published.get_day_type(day)

        market = def_functional_calendar(CalendarID("PUBLISHED_MARKET"), classify)
        assert await market.get_day_type(date(2023, 1, 2)) is DayType.BusinessDay
        assert await market.get_day_type(date(2024, 1, 1)) is DayType.Holiday
        assert await market.get_day_type(date(2024, 2, 18)) is DayType.BusinessDay
        assert await market.get_day_type(date(2025, 1, 1)) is DayType.Undefined
        assert await next_known_business(market, date(2023, 12, 29)) == date(2024, 1, 2)

        for start, message in (
            (date(2024, 12, 31), "calendar not published for 2025-01-01"),
            (date.max, "date range exhausted"),
        ):
            try:
                await next_known_business(market, start)
            except LookupError as error:
                assert str(error) == message
            else:
                raise AssertionError("unknown or out-of-range date must stop the search")


asyncio.run(main())
```

2023 is published even though it has no exception rows, so Monday January 2
uses the weekday rule. The 2024 exceptions close New Year's Day and open a
Sunday. The search from December 29, 2023 checks the weekend and the 2024
holiday before returning January 2. The search from December 31, 2024 stops at
the first 2025 candidate because 2025 has no publication record; the `date.max`
case stops before overflowing. The helper searches strictly after its input.
If the input itself must be known, check it separately. It also stops after
1,000 candidates and propagates database or classifier failures instead of
converting them into weekdays. Built-in `next_bd`, `prev_bd`, inclusive
navigation and mapping operations do not use this helper automatically. If
the application needs fail-closed backward, inclusive, or multiple-step
navigation, implement and test those operations with the same candidate checks.

Treat publication status as authoritative only after the corresponding data is
complete. In an application, read status and rows from a consistent database
revision, then keep that revision stable while the calendar is used. How to
pin one revision or transaction across years depends on the data source. This
example snapshots the publication set and keeps its in-memory connection open
until all lookups finish. SQLite access here is synchronous and blocks the
event loop; use an appropriate asynchronous client for slow database calls.

## Refresh calendars and their dependants

Functional search caches classified dates, and year-batch lookup caches loaded
years. Mapping and composition objects can also retain snapshots. Changing a
source does not update those snapshots or existing references. Recreate the
source calendar and each dependent composition or mapping when a source revision
changes; publish the new objects to consumers together. Use distinct stable IDs
for different policies or configurations. A replacement for the same named
policy can retain its ID, but do not combine old and new instances with that ID:
equality and composition deduplication use the ID.

For manager-owned calendars, coordinate refresh with active work: stop new
business operations, wait for all operations using the old calendar and its
connection and for in-flight loads to finish, update the source, call
`await manager.retire_calendar(calendar_id)`, then reload the named calendars
and rebuild or reacquire dependent combinations before resuming consumers.
Retirement removes cached recursive dependants known through their dependency
IDs; it cannot replace Python references already held by callers or cancel an
in-flight load. If the application cannot pause, give each published policy
revision its own ID and route each operation consistently to one revision. Keep
old calendar objects and their connections alive until operations using that
revision finish, then release those resources.

The manager shares an in-flight named load per ID and event loop and caches
successful loads. That guarantee does not extend to functional per-date or
year-batch cache misses; concurrent calls may repeat source work. Serialize
source access or provide suitable concurrency control when needed. A failed
load is not a valid year snapshot. Handle the failure at the application
boundary and retry or report it according to the source's policy rather than
substituting an unverified fallback.

[Previous: Workflow status](10-workflow-status.md) | [Next: Production patterns](12-production-patterns.md) | [Return to the series introduction](README.md)
