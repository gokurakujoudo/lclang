# Runtime API guide

## Import layers

The package root exposes the daily workflow: `Module`, `Frame`, `FrameFactory`,
`Preset`, `EvaluationLimits`, `DependencySnapshot`, and `STANDARD_PRESET`, plus
the language parser/evaluator, identifier types, source values, and errors.

Use `pylcl.runtime` for advanced static graph construction, topological order,
dynamic tracing, reconciliation values, and standard runtime types. Use
`pylcl.stdlib` for manifests, namespace assembly, individual reviewed helpers,
`STANDARD_MANIFESTS`, and `STANDARD_PRESET`.

## Module, Preset, and FrameFactory

`Module` copies a name-to-AST mapping into a read-only snapshot. `Preset` does
the same for host bindings; `overlay` is shallow and right-biased. A
`FrameFactory` retains a Module, optional Preset, and optional default
`EvaluationLimits`. Each `create` call has fresh cache, task, dependency, and
lifecycle state. Call-level values and limits override factory policy. Parent
Frames are borrowed, not owned.

## Frame caching and concurrency

`await frame.get(name)` lazily evaluates a local definition once, caching either
its result or ordinary failure. Concurrent callers in one event loop share one
owner task. Waiter cancellation is isolated. Circular dependency paths raise a
structured error before an owner can deadlock. Parent definitions always run in
their defining Frame.

`await frame.recalculate(name)` atomically replaces only the named definition's
snapshot; it never invalidates a dependant. Old values remain readable during
refresh. Ordinary success/failure replaces value/failure and dependency trace;
owner cancellation preserves the prior snapshots.

## Dependency snapshots

`frame.dependency_snapshot(name)` is synchronous point-in-time inspection. It
returns static edges, observed dynamic edges, and confirmed/inactive/unexpected
reconciliation. Before evaluation all static edges are inactive. Cached reads
do not add observations. Deferred function/generator lookups extend their
defining source's published trace. Parent lookups route to the owner.

## Limits and close

`EvaluationLimits` caps semantic AST depth, node visits, and one materialized
collection. One root evaluation chain shares its task-local budget; cached reads
consume none and recalculate starts fresh.

`await frame.close()` rejects new work, cancels and settles owned tasks, and
cleans cached resources once in reverse acquisition order. It recognizes sync
`close` and async `aclose`. Parent resources remain parent-owned. Cleanup errors
are stable, and cancelling a waiter does not cancel shared close work.

## Standard preset and errors

`STANDARD_PRESET` exposes pure-data `iter`, `text`, `data`, and `json`
namespaces. It has no file, environment, network, subprocess, reflection, or
dynamic-import helpers. Individual helpers validate their input protocols and
their failures become source-aware structured evaluation failures at the
interpreter boundary.

LCL is for trusted application configuration. It is not a security sandbox for
hostile expressions. Values and callables supplied by the host can execute
ordinary Python behaviour, including blocking or side effects, so applications
must review their own Presets.
