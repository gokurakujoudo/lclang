# Business Day Calendar Reference

`lclang.utils.calendar` is an async-first, three-state calendar algebra. A
calendar maps every `datetime.date` to `DayType.BusinessDay`, `DayType.Holiday`,
or `DayType.Undefined`. Undefined means that the calendar has no opinion; it is
not another spelling for holiday.

## Identity, dates, and failures

Every `BDCalendar` has one immutable `CalendarID`. Equality, hashing, manager
caches, dependency sets, and canonical compositions use that ID. Configuration
collections are detached and read-only. Classification and mapping caches are
mutable implementation snapshots exposed through read-only views.

`get_day_type(d)` classifies a date. `next_bd(d)` and `prev_bd(d)` are strict;
`this_or_next_bd(d)` and `this_or_prev_bd(d)` retain `d` when it is already a
business day. Functional and year-batch traversal searches at most
`MAX_BUSINESS_DAY_GAP_DAYS` (1,000) days. `gen_year(year)` accepts years 1
through 9999 and may omit undefined dates.

- `DateOperationOutOfScopeException` retains `source_date` and `source_calendar`.
- `CalendarCannotLoadException` retains the requested `calendar_id`.
- `CalendarLogicException` retains the failing `calendar_id` and chains the
  original traceback.
- `UnappliedCalendarOperationException` reports a mapping without a source.

These are ordinary Python exceptions. Through LCL, the evaluator wraps them in
its normal source-aware `LclEvaluationError`.

## Storage strategies

`HardcodedBDCalendar` stores an immutable explicit mapping; missing dates are
undefined. `FunctionalBDCalendar` supplies bounded traversal around an abstract
per-date classifier. `ForwardStepBDCalendar` discovers a sparse increasing
business-date sequence from `first_bd`. `YearBatchBDCalendar` loads and caches
one validated mapping per year. Custom subclasses implement the public abstract
method named by their strategy and honor the cache and failure contract.

## Calendar algebra

| Method | Operator | Meaning |
| --- | --- | --- |
| `union` | `+` | Business wins, then holiday, then undefined. |
| `intersect` | `&` | All-undefined stays undefined; any holiday vetoes. |
| `minus` | `-` | Matching subtrahend business days become holidays. |
| `fallback` | `>>` | Return the first non-undefined value in order. |
| `revert` | `~` | Exchange business and holiday; retain undefined. |

Union, intersection, and subtraction operands are sorted and deduplicated by
calendar ID. Fallback order is significant. `business_days()` removes holiday
classifications; `holidays()` removes business classifications. Repeated
filters are idempotent, and double reversal returns the original calendar.

## Builtins and factories

Total singletons are `ALL_DAYS`, `ALL_WEEKDAYS`, `MONDAYS` through `SUNDAYS`,
`BEGIN_OF_MONTHS`, `END_OF_MONTHS`, `BEGIN_OF_YEARS`, and `END_OF_YEARS`.
Nonmatching dates are holidays. `BUILTIN_CALENDARS` maps every singleton ID to
that exact object.

`at(*dates)` accepts `date`, strict `YYYYMMDD` strings, or padded integers.
`nth_day_of_month(*n)` and `nth_business_day_of_month(calendar, *n)` accept
`-31..-1` and `1..31`; negative values count backward. `range_start_days` and
`range_end_days` select boundaries of contiguous business ranges.
`def_functional_calendar` accepts sync or async classifier and dependency
callables and validates their results.

## Date mappings

`map_this_or_next(calendar=None)`, `map_this_or_prev(calendar=None)`, and
`shift_n_days(n, calendar=None)` create immutable `BDCalendarMapping` chains.
Omitting the operation calendar binds it to the source. A standalone chain may
use `SELF_CALENDAR` until `await mapping.apply(calendar)` supplies the source.

Each primitive moves at most `MAX_BUSINESS_DAY_SHIFT_DAYS` (100) calendar days;
a chain may accumulate more. Zero shift has this-or-next semantics. Positive
and negative values use strict next and previous dates. `map_date_reverse`
returns the inclusive monotonic source range mapped to a target.

`await mapping.as_calendar()` creates a `CalendarMapBDCalendar`. A target is
business only when at least one source business date maps to it.

## Named loading and retirement

`BuiltinBDCalendarLoader` returns singleton builtins.
`FileSystemHardcodedBDCalendarLoader` looks for
`<calendar-id>.calendar.json` beneath its configured directory:

```json
{
  "business_days": ["20240102", "20240103"],
  "holidays": ["20240101"]
}
```

The UTF-8 JSON object has exactly those arrays. Dates are unique strict strings
and cannot overlap. Malformed, unsafe, or non-file matches raise
`CalendarCannotLoadException`; absence lets the next loader try.

`BDCalendarManager.use_calendar` shares one in-flight load per ID and event
loop, shields waiter cancellation, caches only success, detects dependency
cycles, and validates returned IDs. Calendar fallbacks are uncached; ID
fallbacks recurse. `retire_calendar` removes a cached calendar and recursive
dependants, optionally installing a replacement.

`use_calendar_manager(loaders)` appends a builtin loader last when needed.
`use_file_system_hardcoded_calendar_loader(path)` accepts `Path` or text.

## LCL exposure

Canonical Frames expose the manager helpers and a read-only `calendars`
namespace from `LCL_BUILTINS`. It contains `DayType`, all factories, and every
singleton. Use `calendars.DayType.BusinessDay`. Standard `iter`, `text`, `data`,
and `json` namespaces also live in `LCL_BUILTINS`; `LCL_ROOT` contains only
definition-scoped `lhs()`.
