# M037: per-name task single-flight and cycle detection

## Goal

Coordinate concurrent lookups so one definition has one owner evaluation while
detecting dependency cycles before they can deadlock on an in-flight Task.

## Module and test layout

- `pylcl/runtime/frames.py` coordinates per-name owner tasks.
- `pylcl/runtime/flight.py` owns task-local dependency paths and diagnostics.
- `tests/runtime/test_flight.py` mirrors concurrent success/failure sharing,
  direct cycles, indirect cycles, and independent Frame isolation.

## Contract

- Within one event loop, simultaneous requests for the same uncached definition
  share one owner `asyncio.Task`; the definition executes exactly once.
- Every waiter receives the same result identity or cached exception identity.
- Single-flight state is owned by the defining Frame, including when requests
  arrive through descendants.
- A task-local dependency path tracks `(Frame, variable)` ownership. Requesting
  an active path entry raises `LclCircularDependencyError` immediately with a
  readable ordered cycle and the requesting name-node span.
- Direct and indirect cycle failures enter the ordinary failure cache. Equal
  names in distinct Frames do not constitute a cycle.
- M037 does not isolate shared owner Tasks from waiter cancellation; M038 adds
  that guarantee explicitly.
- Frame use remains restricted to concurrent tasks in one event loop. Public
  rST documentation and the 200-line source limit remain mandatory.

## TDD evidence

RED requires concurrent calls to execute more than once and cyclic definitions
to recurse/deadlock or lack structured diagnostics. GREEN requires all focused
coordination cases. DONE requires the complete quality gate and synchronized
documentation.
