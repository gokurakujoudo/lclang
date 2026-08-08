# M041: Frame close lifecycle and resource cleanup

## Goal

Give each Frame an idempotent asynchronous close boundary that stops owned work,
releases owned cached resources exactly once, and permanently rejects lookup.

## Module and test layout

- `pylcl/runtime/frame/lifecycle.py` owns close state, task cancellation, cache commit
  retirement, resource deduplication, and cleanup execution.
- `pylcl/runtime/frame/closing.py` exposes `closed` and `close`; the core checks state
  at every lookup/recalculation boundary, and delegates atomic cache commits.
- `tests/runtime/frame/test_lifecycle.py` mirrors close rejection, cancellation,
  sync/async cleanup, ordering, deduplication, failures, hierarchy, refresh
  retirement, idempotence, and close-waiter cancellation.

## Contract

- `Frame.closed` is false until cleanup finishes and true thereafter.
  Beginning close immediately rejects `get`, evaluator `resolve`, and
  `recalculate` with source-aware `LclClosedFrameError` where a span exists.
- `await Frame.close()` is idempotent and concurrency-safe. Concurrent callers
  share one close Task; cancelling a close waiter does not cancel cleanup.
- Close cancels and awaits every definition/refresh owner Task belonging to the
  Frame. Owner `finally` blocks finish before cached resources are released.
- Cached results are Frame-owned. Results displaced by recalculation success or
  failure are retained as retired resources until close. Host bindings and
  parent Frames are borrowed and never closed by this Frame.
- Resources are visited in reverse ownership order and deduplicated by identity.
  A callable `aclose` is preferred over `close`; either result is recursively
  auto-awaited. Values with neither method require no action.
- Every resource is attempted even if another cleanup fails. The first ordinary
  cleanup failure is exposed as `LclEvaluationError` with its cause after the
  Frame becomes closed. Repeated close calls re-raise the same close outcome and
  never rerun cleanup.
- Closing a child leaves its parent usable. Closing a parent makes later child
  fallback fail with that parent's `LclClosedFrameError`.
- Cache, failure, in-flight, refresh, and retired-resource state is cleared once
  cleanup settles. Direct cancellation raised by a resource cleanup does not
  leave the Frame half-open; cleanup continues under the owned close Task.
- Public methods use complete English rST documentation; implementation and
  mirrored test modules remain below 200 physical lines.

## TDD evidence

RED requires close lifecycle tests to fail because `Frame.close`/`closed` are
absent. GREEN requires all ownership, cancellation, cleanup, error, and
hierarchy cases. DONE requires the complete quality gate and synchronized
README/progress documentation.
