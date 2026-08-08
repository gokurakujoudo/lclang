# M045: Frame dependency snapshots and recalculation integration

## Goal

Integrate static graphs and runtime traces into `Frame` so callers can inspect
immutable per-definition dependency snapshots that remain consistent with
cached evaluation and atomic recalculation outcomes.

## Module and test layout

- `pylcl/runtime/dependency/snapshot.py` owns the public immutable snapshot.
- `pylcl/runtime/frame/dependencies.py` owns graph/trace staging, publication,
  reconciliation, hierarchy-neutral lookup, and cleanup support.
- `pylcl/runtime/frame/evaluation.py` installs a tracing resolver for each
  definition evaluation; the dependency mixin exposes owner-aware snapshots.
- Matching `tests/runtime/dependency/test_snapshot.py` and
  `tests/runtime/frame/test_dependencies.py` mirror value and Frame behaviour.

## Contract

- `DependencySnapshot(source, static_edges, dynamic_edges, reconciliation)` is
  immutable point-in-time evidence. The source and all static edges belong to
  that definition; all dynamic edges have kind `dynamic`; reconciliation must
  equal those two edge collections. Invalid manually constructed snapshots are
  rejected.
- `Frame.dependency_snapshot(name)` validates a non-empty name and rejects a
  closing/closed Frame. A local definition returns its current snapshot; a
  parent-owned definition delegates to its owner. Host-only names raise
  `LclEvaluationError`; unknown names raise `LclNameError`.
- Before first evaluation, a definition snapshot contains its complete static
  edges, no dynamic edges, and every static edge is inactive.
- Each definition evaluation uses a fresh candidate `DependencyTrace` through a
  `TracingResolver`. Nested definition evaluation therefore attributes each
  lookup to its actual defining source, while cached dependency lookup remains
  observable from the dependant.
- An ordinary successful or failed initial evaluation publishes its candidate
  trace in the same non-awaiting commit section as its cached result or failure.
  Owner cancellation or other direct `BaseException` publishes nothing.
- Recalculation stages a fresh trace. Ordinary success or failure atomically
  replaces the prior trace with the new cached outcome. While recalculation is
  in flight, ordinary lookup and snapshot inspection continue seeing the old
  value/failure and old trace. Cancelled recalculation preserves both.
- A published trace is retained by reference. Deferred closure or generator
  lookup after definition evaluation extends the next snapshot without changing
  any previously returned snapshot.
- Repeated cached `Frame.get` calls do not evaluate and do not mutate traces.
  Recalculation still never invalidates dependant values or dependency traces.
- Closing the Frame clears owned trace references after lifecycle settlement;
  parent-owned snapshots and resources remain owned by the parent.
- Public APIs use complete English rST documentation. All production and
  mirrored test modules remain below 200 physical lines.

## TDD evidence

RED requires snapshot exports and `Frame.dependency_snapshot` to be absent.
GREEN requires validation, pre/post evaluation evidence, nested attribution,
ordinary failure, closure growth, cached stability, hierarchy routing, atomic
success/failure replacement, cancellation preservation, and closed-Frame
rejection. DONE requires the complete quality gate and synchronized bilingual
README/progress documentation.
