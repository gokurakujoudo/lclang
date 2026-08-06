# M030: primary access and call evaluation

## Goal

Evaluate chained attributes, null-safe access, subscriptions, slices, and calls
with deterministic receiver/argument order and async-aware results.

## Module and test layout

- `pylcl/lang/evaluator/primaries.py` owns attribute, safe attribute, subscript,
  and semantic slice evaluation; its mirror covers chains, null behaviour,
  order, and protocol errors.
- `pylcl/lang/evaluator/calls.py` owns callable resolution and all four argument
  wrappers; its mirror covers order, sync/async expansion, duplicates, and
  automatically awaited results.
- Central dispatch recognizes the families and delegates recursive children.

## Contract

- Ordinary attributes use `getattr`. Safe attributes return `None` without
  access only when the resolved receiver is exactly `None`; they do not suppress
  `AttributeError` or other descriptor failures.
- Subscriptions evaluate receiver before index. Semantic slices evaluate lower,
  upper, then step and produce a built-in `slice`; tuple indices retain tuples.
- Calls evaluate the callable first, then argument wrappers left-to-right.
  Positional and keyword values are fully awaited before the call.
- `*` arguments consume sync or async iterables. `**` arguments require a
  mapping with string keys. Duplicate keyword names raise `TypeError` before the
  callable runs.
- Sync callables run inline because inputs are trusted application values.
  Awaitable call results are automatically resolved by central evaluation.
- Descriptor, subscription, iteration, callable, and user-function exceptions
  propagate unchanged until M032's wrapping boundary.
- Complete English rST docstrings and the 200-line source limit remain enforced.

## TDD evidence

RED requires mirrored primary/call cases to fail with unsupported-node errors.
GREEN requires every access and argument form plus ordering and async cases.
DONE requires the complete quality gate and synchronized documentation.
