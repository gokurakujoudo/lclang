# Standard and Workflow Utilities

## Builtin values

The canonical runtime hierarchy exposes these value types:

`bool`, `bytes`, `dict`, `float`, `frozenset`, `int`, `list`, `set`, `str`, and
`tuple`.

It also exposes these functions:

`abs`, `all`, `any`, `bin`, `chr`, `divmod`, `enumerate`, `filter`, `format`,
`hex`, `isinstance`, `len`, `map`, `max`, `min`, `oct`, `ord`, `parse_ymd`,
`pow`, `range`, `recursive`, `repr`, `reversed`, `round`, `slice`, `sorted`,
`sum`, `to_ymd`, and `zip`.

`parse_ymd` converts strict `YYYYMMDD` integers to dates and `to_ymd` performs
the reverse conversion. `recursive(builder)` returns an eager fixed-point
function suitable for recursive LCL programs.

## Standard namespaces

`STANDARD_PRESET` supplies read-only namespaces assembled from reviewed
manifests. Canonical Frames merge those bindings into `LCL_BUILTINS`:

- `iter.collect` and `iter.first` consume synchronous or asynchronous iterables.
- `text.join` and `text.lines` provide deterministic text operations.
- `data.lookup` and `data.merge` work with immutable mapping snapshots.
- `json.encode` and `json.decode` provide strict JSON conversion.

These helpers do not provide ambient filesystem, process, network, dynamic
import, reflection, or mutation capabilities.

Canonical Frames also expose the reviewed `calendars` namespace and explicit
calendar-manager construction helpers. Filesystem access remains opt-in through
`use_file_system_hardcoded_calendar_loader`; see the
[business day calendar reference](calendar.md).

Python integrations may import `STANDARD_MANIFESTS`, `STANDARD_PRESET`,
`StdlibEntry`, `StdlibManifest`, `StdlibNamespace`, `RecursiveFunction`,
`assemble_stdlib`, `collect`, `first`, `join`, `lines`, `lookup`, `merge`,
`json_encode`, `json_decode`, and `recursive` from `lclang.stdlib`.

## Environment and logging utilities

`from lclang.utils import env` returns the singleton live `Environment` view.
`env.NAME` and `env.get(name, default=None)` consult `os.environ` at each call;
missing names return the default and reads never snapshot or mutate the process
environment. The canonical LCL `env` utility adds scoped Frame overrides on top
of this view.

The same module exports `DEFAULT_LOG_FORMAT`, `LogConfig`, `LoggerHandle`, and
`async create_logger(config, name)`. `LogConfig` validates a disabled or file
logging policy without touching the filesystem. `create_logger` creates an
isolated, non-propagating standard-library logger and returns its owned handle;
`LoggerHandle.close()` detaches and closes handlers idempotently. This surface
does not require an lclang CLI application. `lclang.cli.LogConfig` remains a
compatible export, and the CLI materializes its scoped `logger` proxy with
`as_record(LogConfig)` before delegating file handler creation to this utility.

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
