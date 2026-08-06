# M039: atomic explicit recalculation

## Goal

Refresh one definition on demand while keeping its previous snapshot readable
until a complete new success or failure can replace it atomically.

## Module and test layout

- `pylcl/runtime/frames.py` exposes refresh dispatch and cache commit helpers.
- `pylcl/runtime/recalculation.py` coordinates one refresh owner per definition.
- `tests/runtime/test_recalculation.py` mirrors atomic replacement, parent
  ownership, and dependant snapshot retention.
- `tests/runtime/test_recalculation_flights.py` mirrors initial-owner waiting,
  refresh coalescing, failure/cancellation settlement, and waiter isolation.

## Contract

- `await Frame.recalculate(name)` requires a non-empty name and explicitly
  re-evaluates the definition that owns that name. A child delegates a
  parent-owned definition to the parent Frame.
- Host bindings are immutable Frame inputs rather than definitions and cannot
  be recalculated. Attempting to do so raises `LclEvaluationError`; an unknown
  name raises `LclNameError`.
- If the definition has an initial owner evaluation in flight, recalculation
  waits for that owner to settle before starting a distinct refresh.
- Concurrent recalculation calls for the same definition share one refresh
  Task and receive the same result or exception instance.
- While a cached success or failure is being refreshed, ordinary `get` calls
  continue observing that previous snapshot. The new outcome is committed only
  when evaluation settles.
- A refresh success stores its result and removes the prior failure. An ordinary
  refresh failure stores that exact exception and removes the prior result.
- Direct `BaseException` cancellation is not committed. The previous snapshot
  remains visible and a later recalculation can retry.
- Recalculation replaces only the requested definition. Cached dependants are
  never invalidated or recomputed, even when they previously read that name.
- Refresh evaluation retains task-local cycle detection, parent ownership,
  waiter shielding, strict typing, English rST docs, and the 200-line limit.

## TDD evidence

RED requires focused tests to fail because `Frame.recalculate` is absent. GREEN
requires all atomic replacement, isolation, and ownership cases. DONE requires
the complete quality gate and synchronized README/progress documentation.
