# lclang

**A typed, async-first configuration expression language for Python.**

`lclang` gives applications a disciplined way to express calculated
configuration, evaluate it only when needed, and explain where every result
came from. It occupies the useful space between static data files and putting
all configuration logic in Python.

LCL stands for **Lazy Context Language**:

- **Lazy** definitions run only when a requested result depends on them.
- **Context** comes from a short-lived Frame containing host inputs, lookup
  hierarchy, cached results, dependency evidence, and owned async work.
- **Language** means rules are parsed into an immutable syntax tree and run by
  lclang's own interpreter, rather than hidden in string substitution or
  application glue.

The package includes the expression language, reusable Modules and Frames,
UTF-8 `.lclcfg` files, dependency analysis, runtime inspection, reviewed
standard namespaces, a typed command-line framework, tree workflows and status,
and a composable business-day calendar system.

## Why lclang

Static formats are excellent for static values. They become awkward when a
configuration needs derived names, conditional policy, reusable functions,
request-specific inputs, or an explanation of why a value has its current
form. Plain Python can calculate all of that, but it also makes the boundary
between policy and application behavior easy to blur.

lclang provides a strong way of working while leaving room for each application
to supply its own values and callables:

- Parse rules once, then reuse them safely across independent runs.
- Keep stable policy separate from request, tenant, command, or environment
  inputs.
- Evaluate only the dependency path needed for the requested output.
- Share concurrent work and cache value or failure snapshots predictably.
- Inspect definitions, owners, cache states, lookup paths, and dependencies.
- Compose configuration files without losing source and history information.
- Use the same evaluation model in services, batch jobs, CLIs, and tests.
- Stay fully typed with no third-party runtime dependencies.

This makes lclang especially useful for deployment policy, derived service
settings, pricing and eligibility rules, command defaults, scheduling logic,
and other trusted configuration that has real relationships between values.

## Installation

```console
python -m pip install lclang
```

## Start in 60 seconds

Define a reusable Module once. Create a fresh Frame for one calculation, supply
the values owned by the application, and ask only for the outputs you need.

<!-- lclang-readme-exec -->
```python
import asyncio

import lclang


ORDER = lclang.define_module(
    "order",
    {
        "subtotal": "unit_price * quantity",
        "shipping": "0 if subtotal >= 50 else 5",
        "total": "subtotal + shipping",
        "summary": 'f"{quantity} items: {total:.2f}"',
    },
)


async def main() -> None:
    async with lclang.define_frame(
        ORDER,
        preset={"unit_price": 13, "quantity": 3},
    ) as frame:
        assert await frame.get("subtotal") == 39
        assert await frame.get("total") == 44
        assert await frame.get("summary") == "3 items: 44.00"


asyncio.run(main())
```

The first lookup multiplies the two host inputs and stores `subtotal` as a
snapshot. The `total` lookup reuses that snapshot, takes the false branch of the
shipping condition because 39 is below 50, and adds 5. The final lookup follows
`summary -> total -> subtotal`; the previously calculated values are reused, and
the f-string formats 44 with two decimal places.

Definition order is not evaluation order. Every expression is parsed and
validated when the Module is created, while evaluation follows name lookups
from the requested result.

For a single expression in synchronous code, use the smaller boundary:

<!-- lclang-readme-exec -->
```python
import lclang

total = lclang.evaluate_sync(
    "unit_price * quantity",
    {"unit_price": 6, "quantity": 4},
)
assert total == 24
```

Do not call `evaluate_sync()` from a running event loop. Async applications
should use Frames or await `evaluate()`.

## The Module and Frame model

Most integrations need only two concepts.

### Module: what can be calculated?

A `Module` is an immutable collection of named, unevaluated definitions. It has
no per-run cache or lifecycle state, so the same Module can be reused across
requests, tenants, commands, and tests.

### Frame: what do those definitions mean now?

A `Frame` combines a Module with concrete host inputs, parent lookup, lazy
result snapshots, dependency observations, and owned asynchronous work. It is
stateful, belongs to one event loop, and should normally represent one
independent run.

Scoped values organize larger policies without creating nested Frames. A flat
binding such as `service.database.port` makes `service` and
`service.database` lazy proxies over the same requesting Frame. For a quick
unnamed calculation over that context, use
`await frame.evaluate("service.database.port * 2")`; unlike `frame.get`, the
unnamed root is parsed and run on every call.

```text
expression source -> immutable Module
immutable Module + host inputs -> short-lived Frame -> requested results
```

Use `async with` so owned work and async context managers close
deterministically. A Frame is safe for concurrent tasks in the same event loop,
but not across different loops.

The first `await frame.get(name)` calculates and stores either a value or an
ordinary failure. Concurrent callers share the in-flight work. Later reads get
the same snapshot. This is deliberate: a Frame is a reproducible calculation
run, not a reactive spreadsheet.

Changing an input does not silently invalidate dependants. Recalculation is
explicit and local:

```python
frame.mixin({"unit_price": 10})
await frame.recalculate("subtotal")
await frame.recalculate("total")
```

If several related inputs change, creating a new Frame is often clearer. Use
`mixin()` and `recalculate()` when retaining the other snapshots in the current
run is intentional.

## Feature tour

### Expression language

LCL is expression-only, Unicode-aware, and intentionally familiar to Python
users. It supports arithmetic, comparisons, short-circuit Boolean logic,
conditionals, null coalescing, safe attributes, calls, slices, unpacking,
collection displays, comprehensions, generators, f-strings, exceptions,
immutable named records, context managers, and sync or async iteration.

```lcl
profile?.display_name ?? "anonymous"
{name=profile.name, active=true}.name
[item * 2 for item in values if item > 0]
f"{service}: {port}"
(left, right=10) -> left + right
try primary() except ServiceError: fallback()
```

Arrow functions provide defaults, keyword arguments, lexical closures, and
recursive-program support. `parse_expression()` returns immutable syntax,
`to_source()` renders canonical source, `evaluate()` is the async evaluation
boundary, and `evaluate_sync()` is the synchronous convenience boundary.

### Configuration files with provenance

`.lclcfg` files move definitions outside Python while preserving file, line,
override, and inclusion history.

```lclcfg
__LCL_VERSION__: 1

service: "catalog"
port: 8443
host: f"{service}.{environment}"
address: f"{host}:{port}"
```

The application supplies `environment`; the file owns the stable relationship
between it and the final address. Definitions can refer forward or backward.
`using` declarations expand other `.lclcfg` files in source order, later
definitions win, and complete history remains available for diagnostics.

```python
from pathlib import Path

from lclang.config import evaluate_config, load_config


async def address_for(environment: str) -> str:
    config = await load_config(Path("settings.lclcfg"))
    result = await evaluate_config(
        config,
        "address",
        values={"environment": environment},
    )
    assert isinstance(result, str)
    return result
```

Loading is asynchronous, UTF-8, bounded by configurable limits, cycle-aware,
and concurrency-sharing. It performs no globbing, environment expansion,
network access, or evaluation while files are being composed.

For readable configuration, keep definitions from one scope on consecutive
rows, separate functional or scope groups with a blank line, and describe rows
or groups with `#` comments. Qualified leaves infer their prefixes, so explicit
`FRAME_PROXY` declarations remain supported but are not recommended for an
ordinary file layout.

### Dependency analysis and runtime inspection

lclang can explain calculated configuration instead of treating it as a black
box.

- Static analysis classifies eager, conditional, and deferred references.
- Module and Frame graphs support filtered queries and deterministic
  topological ordering.
- Runtime tracing records the names actually selected during evaluation.
- Dependency snapshots reconcile static possibilities with observed work.
- `frame.get_definition(name)` returns selected syntax without evaluating it.
- `frame.inspect_variable(name)` builds a detached tree of owners, lookup paths,
  cache states, values, failures, and dependency descendants.

```python
tree = frame.inspect_variable("total")
print("\n".join(tree.to_lines()))
```

Syntax, name, evaluation, circular-dependency, closed-Frame, and configuration
failures use specific `LclError` subclasses. Source-aware errors retain the
variable evaluation stack so application boundaries can report useful context.

### Async-first evaluation

Resolver values, host callables, call results, iterators, and context-manager
protocols may be synchronous or asynchronous. lclang awaits them when needed
and keeps cancellation isolated between the owner of a calculation and other
tasks waiting for it.

Task-local evaluation limits can bound work. Circular lookups produce a named
dependency path. Frame closing finalizes owned resources deterministically.
These properties let the same policy work naturally in an async service without
making simple synchronous scripts cumbersome.

### Reviewed standard namespaces

Canonical Frames include familiar pure builtins plus small, read-only
namespaces assembled from reviewed manifests:

- `iter.collect` and `iter.first` consume sync or async iterables.
- `text.join` and `text.lines` provide deterministic text operations.
- `data.lookup` and `data.merge` work with immutable mapping snapshots.
- `json.encode` and `json.decode` provide strict JSON conversion.
- `parse_ymd` and `to_ymd` convert strict calendar-date integers.
- `recursive` builds eager fixed-point functions for recursive LCL programs.

They provide no ambient filesystem, process, network, dynamic import,
reflection, or mutation capability.

### Command-line applications

`lclang.cli` is a typed async framework for Python scripts whose parameters may
come from declared defaults, `.lclcfg` files, and command-line overrides. A
decorated command handler receives one `CliContext`, including its invocation
Frame, as-of date, dry-run flag, and logging context, and returns a deterministic
`CliResult`.

The framework provides immutable invocation values, nested command groups,
structured help, full-argument parsing, platform-neutral process entry points,
alphabetized configuration-parameter help, isolated formal file logging, and
opt-in internal tracing. Logger settings use scoped configuration names such as
`logger.log_dir`. Non-error application records print to stdout, application
errors print to stderr, and `--verbose` adds `DEBUG` records to stdout,
independently of file logging. File and terminal application records share the
configured structured format, including time, level, source location,
function, and message; the default no longer appends logging argument tuples.
Logger expressions can use the reserved values `__as_of_date__`, `__dryrun__`,
`__verbose__`, `__ymd__`, `__execution_timestamp__`, and `__command__`; public
Python constants provide every runtime key, including `__cli_params__`. Enabled
file logs begin
with four readable audit records: their bound path, a centered multi-line
execution banner, exact JSON argv with masked override redaction, and sorted,
aligned winning configuration. The configuration audit renders lazy LCL source
without evaluating expressions or warming caches. Pass `--verbose` after a
selected command to trace expression parsing, value provenance, caching, fallbacks, and
evaluation to stderr; enabled file logging receives the same records. Trace
values use bounded representations. A trailing `!` on a definition or binding
key, such as `api_token!: load_token()`, keeps the runtime name `api_token` but
renders its parse, evaluation, lookup, cache, failure, and inspection payloads
as `*masked*`. The marker is exact-name and sticky across overrides; derived
keys require their own marker. Application-authored log messages remain the
handler's responsibility. The existing `-v/--version` spelling remains the
version command. Precedence rises from preset and command defaults through
configuration definitions and command-line overrides to reserved runtime
values. Built-in commands inventory available values, parse LCL, and evaluate
LCL using the same routing model.

Dry-run remains an explicit handler decision, so the framework never pretends
to know whether an application-specific side effect is safe.

### Tree workflows and status

`lclang.workflow` defines a validated tree of typed async actions. Plain
dataclass mappings connect named `TaskVar` values to arguments and explicitly
publish outputs. Each node can own async context tasks for local resources or
exception handling, followed by ordered child tasks. Execution is parent-first,
depth-first against one shared Frame; task-local Frames confine context outputs,
while mapped action outputs can feed later nodes.

The fixed tree, scope, cleanup, and status rules provide a strong format. Inside
it, actions remain ordinary async Python and can use application-specific
services or detailed status steps. `workflow.to_lines()` renders the static tree
and field flows. `workflow.to_cli()` infers external parameters, help, and
masking, and `lclang.cli.scan_commands()` discovers commands in a package.

Execution records nested task and step outcomes, including visible covered
failures, skipped branches, and error origins. Contexts unwind in reverse order,
and the result retains the final status tree plus every successful action's
materialized arguments and outputs. CLI workflows log start, traceback-bearing
error, and finalized completion records using dot-connected task branches;
`__task_id_branch__` exposes the owning branch inside task Frames. Verbose runs
add aligned typed argument/output mappings. The final status tree is one
severity-aware multi-line record, followed by an optional configured lunch
choice on success or `no lunch!` on non-success.

### Business-day calendars

`lclang.utils.calendar` provides an async-first, three-state calendar algebra.
Every date is a business day, holiday, or undefined; undefined means that the
calendar has no opinion and enables meaningful composition.

Calendars support union, intersection, subtraction, ordered fallback, reversal,
business-only and holiday-only filters, bounded date movement, immutable date
mappings, built-in weekday and period-boundary calendars, strict JSON loading,
concurrent named-calendar caching, and dependency-aware retirement. Canonical
Frames expose the reviewed factories and singletons through the `calendars`
namespace.

The calendar layer works as a Python utility in its own right and also gives LCL
configuration a precise vocabulary for settlement dates, processing windows,
and scheduling policy.

## Choose the smallest entry point

| Need | Preferred API | Ownership model |
| --- | --- | --- |
| One expression in synchronous code | `evaluate_sync(source, values)` | lclang owns the temporary event loop |
| One parsed expression asynchronously | `parse_expression()` then `await evaluate()` | caller supplies resolver values |
| Related named definitions | `define_module()` and `async with define_frame()` | reuse the Module; close each Frame |
| One unnamed expression in an existing context | `await frame.evaluate(source)` | Frame supplies lookup; caller owns the uncached result |
| One value from a config file | `load_config()` then `evaluate_config()` | the temporary Frame is closed for you |
| Many runs with the same policy | `FrameFactory` or `Config.frame_factory()` | each created Frame is caller-owned |
| A typed multi-step operation | `define_workflow()` then `await workflow.execute()` | caller owns the shared execution Frame |
| Syntax printing or analysis | `parse_expression()` and analysis APIs | no evaluation state is created |

For optional lookup, `await frame.get(name, fallback=value)` returns the
fallback only when the name is absent from the complete Frame hierarchy. It
does not hide a definition that exists but fails, and it does not cache the
fallback.

## When lclang fits

Choose lclang when configuration has meaningful relationships and benefits from
lazy evaluation, per-run context, source-aware diagnostics, or dependency
evidence. It is a strong fit when rules should be reusable and inspectable but
host applications must retain control over inputs and capabilities.

Prefer JSON, TOML, YAML, or plain Python data when the input is already static
and has no useful derived relationships. Prefer ordinary Python when the logic
is fundamentally application behavior, needs unrestricted object access, or is
clearer as a normal function than as configuration policy.

## Practical integration rules

1. Parse definitions once and reuse the resulting Module.
2. Create one Frame per independent request, command, tenant, or run.
3. Pass narrow values and purpose-built callables, not broad service objects.
4. Request only the output names the application needs.
5. Treat cached values as snapshots and recalculate explicitly.
6. Use caller-owned Frames as async context managers.
7. Use `evaluate_config()` when only one file-backed value is required.
8. Catch `LclError` at the application boundary and preserve its diagnostic
   context.

## Production characteristics

- Stable 1.0 release line.
- Pure Python for Python 3.14 and newer.
- Fully typed and ships a `py.typed` marker.
- No third-party runtime dependencies.
- Custom lexer, parser, immutable AST, and async interpreter.
- No Python `eval`, `exec`, AST compilation, Java, or generated parser runtime.
- 100% branch coverage enforced by the project quality gate.
- Parser differential and property tests, concurrency and dependency stress
  tests, lifecycle leak checks, and executable documentation.
- Reproducible source distribution and platform-independent wheel validation.

## Trust and security

lclang is a trusted configuration language, not a hostile-code sandbox. Its own
standard values deliberately omit ambient filesystem, process, network,
dynamic-code, and reflection powers. However, expressions can use the values
and callables supplied by the host application, so those inputs determine the
authority available during evaluation.

Treat LCL source, `.lclcfg` files, host objects, and host callables as trusted
application configuration. Keep the Python boundary narrow and use loading and
evaluation limits where bounded work matters.

## Requirements and license

- Python 3.14 or newer
- No third-party runtime dependencies
- MIT license
