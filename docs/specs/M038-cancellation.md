# M038: waiter and owner cancellation isolation

## Goal

Make Frame single-flight robust when individual callers cancel without hiding
genuine cancellation originating inside the owner evaluation.

## Module and test layout

- `pylcl/runtime/frame/evaluation.py` shields owner Tasks at waiter boundaries.
- `tests/runtime/frame/test_cancellation.py` mirrors waiter cancellation, surviving
  peers, owner-originated cancellation, retry, and cache completion.

## Contract

- Every caller awaits an in-flight owner through `asyncio.shield`. Cancelling
  one waiter raises `CancelledError` only in that waiter and does not cancel the
  shared definition Task.
- Other waiters continue and receive the owner's result or ordinary failure.
- If all current waiters cancel, the owner still runs to completion and stores
  its result/failure snapshot for a later lookup.
- Cancellation raised by the definition itself cancels the owner Task and is
  observed by every waiter as direct `CancelledError`.
- Owner cancellation is not cached. In-flight state is removed exactly once and
  a later lookup starts a fresh owner evaluation.
- Shielding does not alter task-local dependency paths, parent ownership, or
  structured cycle detection.
- Public rST documentation and the 200-line source limit remain mandatory.

## TDD evidence

RED requires a cancelled waiter to cancel the M037 shared owner. GREEN requires
isolated waiters, surviving cache completion, owner cancellation propagation,
and successful retry. DONE requires the full quality gate and synchronized
documentation.
