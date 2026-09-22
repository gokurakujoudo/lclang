# Standard and Workflow Utilities

## Invoking Python callbacks

`await lclang.utils.invoke(callback, *args, **kwargs)` calls a synchronous or
asynchronous callable exactly once, then resolves any returned awaitables using
the interpreter's existing awaitable resolver. Its type signature retains the
callback's parameters and final return type. Ordinary values retain identity;
exceptions and cancellation propagate unchanged. The helper creates no thread,
background task, or synchronous event-loop boundary.

## Builtin values

The canonical runtime hierarchy exposes these value types:

`bool`, `bytes`, `dict`, `float`, `frozenset`, `int`, `list`, `set`, `str`, and
`tuple`.

`SnowflakeGenerator` is also available as an explicit stateful utility constructor;
see [Snowflake IDs](#snowflake-ids) below.

It also exposes these functions:

`abs`, `all`, `any`, `bin`, `chr`, `divmod`, `enumerate`, `filter`, `format`,
`hex`, `isinstance`, `len`, `map`, `max`, `min`, `oct`, `ord`, `parse_ymd`,
`pow`, `range`, `recursive`, `repr`, `reversed`, `round`, `slice`, `sorted`,
`sum`, `to_ymd`, and `zip`.

`parse_ymd` converts strict eight-character `YYYYMMDD` strings to dates;
`to_ymd` returns that string format. Integer inputs are rejected. `recursive(builder)` returns an eager fixed-point
function suitable for recursive LCL programs.

## Standard namespaces

`STANDARD_PRESET` supplies read-only namespaces assembled from reviewed
manifests. Canonical Frames merge those bindings into `LCL_BUILTINS`:

- `iter.collect` and `iter.first` consume synchronous or asynchronous iterables.
- `text.join` and `text.lines` provide deterministic text operations.
- `data.lookup` and `data.merge` work with immutable mapping snapshots.
- `json.encode` and `json.decode` provide strict JSON conversion.

The `iter`, `text`, `data` and `json` helpers perform only their documented
operations. The separately exposed `env` utility reads the live process
environment. Calendar file loading can access the filesystem when explicitly
configured by the application. These capabilities follow the trusted-code model.

Canonical Frames also expose the reviewed `calendars` namespace and explicit
calendar-manager construction helpers. Filesystem access remains opt-in through
`use_file_system_hardcoded_calendar_loader`; see the
[business day calendar reference](calendar.md).

Python integrations may import `STANDARD_MANIFESTS`, `STANDARD_PRESET`,
`StdlibEntry`, `StdlibManifest`, `StdlibNamespace`, `RecursiveFunction`,
`assemble_stdlib`, `collect`, `first`, `join`, `lines`, `lookup`, `merge`,
`json_encode`, `json_decode`, and `recursive` from `lclang.stdlib`.

## Snowflake IDs

`from lclang.utils import SnowflakeGenerator` exposes
`SnowflakeGenerator(worker_id, *, epoch_ms=1704067200000)`. The same constructor
is a canonical LCL builtin. Retain one instance and call `generator.next_id()`
to obtain a nonnegative Python integer that fits in a signed 64-bit column.
Construction and generation are synchronous, with no I/O or owned async resources.

The layout is `(elapsed_ms << 22) | (worker_id << 12) | sequence`: 41 bits of
elapsed UTC Unix milliseconds, 10 worker bits, and 12 sequence bits. The default
epoch is 2024-01-01 00:00:00 UTC. The clock is read with integer `time.time_ns()`
conversion, never floating-point seconds. The first sequence in each millisecond
is zero; IDs strictly increase within an instance. Worker zero at the epoch can
produce ID zero. The maximum elapsed time is `2**41 - 1` milliseconds, about
69.7 years after the configured epoch; at most 4096 IDs fit in each millisecond
per worker. These are identifiers, not secrets or cryptographic random values.

Both arguments must be integers excluding bool (`TypeError` otherwise).
`worker_id` must be in `0..1023` and `epoch_ms` must be nonnegative (`ValueError`
otherwise). The read-only properties `worker_id` and `epoch_ms` expose the
validated configuration. Each instance serializes clock reads and state updates
with a thread lock, so Python threads and tasks in different event loops can
share it. It never sleeps or spins waiting for the clock.

`next_id()` raises `ValueError` when the clock precedes the epoch,
`RuntimeError` when it moves behind the last successful millisecond, and
`OverflowError` when the sequence or 41-bit timestamp is exhausted. Failures
leave the last successful timestamp and sequence unchanged. After sequence
exhaustion, the caller may retry when the clock advances; after rollback, it
must wait until the clock catches up (and advances if that sequence was full).
Timestamp exhaustion requires a planned migration to a new ID domain.

Uniqueness across instances is the application's responsibility: use the same
epoch throughout an ID domain and assign distinct worker IDs to concurrent
generators/processes. No worker discovery, coordination, or persistent state is
provided. Do not copy a generator into a forked child or recreate it per ID.
Reusing a worker ID after restart is safe only once wall time is strictly beyond
every timestamp previously emitted by that worker. Changing the epoch does not
preserve uniqueness with old IDs.

In LCL, define `ids: SnowflakeGenerator(worker_id)` once and use
`request_id: ids.next_id()`. A named result is a cached Frame snapshot: repeated
`frame.get("request_id")` returns the same ID, while explicit recalculation
generates another. Do not recalculate the `ids` definition: that resets its state.
For multiple Frames using the same worker, construct the generator in Python
and share it through a preset instead of constructing one in each Frame.
See the [executable Python and LCL examples](../tutorials/16-python-utilities.md#generate-snowflake-ids).

## Environment and logging utilities

`from lclang.utils import env` returns the singleton live `Environment` view.
`env.NAME` and `env.get(name, default=None)` consult `os.environ` at each call;
missing names return the default and reads never snapshot or mutate the process
environment. The canonical LCL `env` utility adds scoped Frame overrides on top
of this view.

Process logging lives in `lclang.logger`. Its two async entry points are
`use_logger_handler(config)` and `use_logger(name=None, prefix="", emit_level=0)`.
The handler scope owns console and named file output and restores stdlib logging
on exit. CLI and Workflow applications resolve the same configuration from LCL
and command-line overrides; see the [logger reference](logger.md).

## Workflow status

`lclang.workflow` exports:

- `ExecutionStatus`: the status value used by tasks and steps.
- `ExecutionTaskType`: task classification.
- `ExecutionStatusTree`: an ordered public record of a task subtree.
- `ExecutionStatusManager`: creates and coordinates nested task cursors.
- `ExecutionStatusStep`: a scoped step whose description and status may be
  updated atomically.

Task and step context managers finalize successful scopes automatically, record
failures, and allow exceptions to propagate. Parent aggregation is
deterministic, subtree operations are locked, and snapshots preserve child
order. `FAILURE_COVERED` records an exception handled by an explicit workflow
context without disguising it as success. See the [workflow reference](workflow.md)
for task definitions, mappings, execution, static rendering, and CLI conversion.

## Safe representations

`lclang.utils.safe_repr(value, *, max_length=200, renderer=None, masked=False)`
returns one physical line without a type prefix or task-local masking state.
It uses `repr` or the supplied `renderer(value)`, escapes CR and LF, and converts
renderer exceptions (including `BaseException`) or non-string results to
`<repr failed: ExceptionType>`. The length budget includes `...<truncated>`;
small budgets retain its prefix, zero returns empty text, and `None` disables
truncation. A negative budget raises `ValueError`; non-integers, including bool,
raise `TypeError`. With `masked=True`, the result is `*masked*` and no renderer
runs; the masking marker is independent of the validated budget.
