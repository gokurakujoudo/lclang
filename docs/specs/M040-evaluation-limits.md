# M040: evaluation depth, work, and collection limits

## Goal

Bound one uncached Frame evaluation chain by deterministic AST depth, semantic
work, and materialized collection-size budgets without affecting unrestricted
standalone language evaluation.

## Module and test layout

- `pylcl/runtime/limits.py` owns immutable public `EvaluationLimits` and mutable
  per-chain budget state.
- `pylcl/lang/evaluator/budget.py` owns an inward-facing guard protocol and
  ContextVar hooks so the language layer never imports runtime.
- `pylcl/lang/evaluator/evaluator.py` accounts for every visited semantic node.
- Collection evaluator modules report materialized result sizes through the
  same language-owned guard hook.
- `tests/runtime/test_limits.py` mirrors validation, depth, work, collection,
  hierarchy, cache, recalculation, cancellation, and task-isolation behaviour.
- `tests/lang/evaluator/test_budget.py` verifies that evaluation without an
  installed runtime guard remains unrestricted.

## Contract

- `EvaluationLimits(max_depth=100, max_steps=100_000,
  max_collection_items=10_000)` is immutable. Every limit must be a positive
  integer; booleans, zero, and negative values raise `ValueError`.
- `Frame(..., limits=...)` retains explicit limits or the defaults. A newly
  started uncached definition or recalculation creates one mutable budget for
  its complete dependency chain.
- If evaluation enters an already-budgeted chain, including a parent-owned
  dependency Task, it inherits the active root budget rather than resetting it.
  Independent owner Tasks receive isolated budgets.
- Depth is the current nested semantic AST-node count. Steps count every node
  visit, including repeated comprehension body/condition evaluation.
- Tuple, list, set, and dictionary displays and materialized comprehensions
  report their result item count. A generator stays lazy and has no materialized
  size until another operation consumes it.
- Exceeding any limit raises source-aware `LclEvaluationError` with a stable
  message naming the exhausted budget. The ordinary Frame failure cache stores
  that error exactly like other evaluation failures.
- Cached lookups consume no new budget. Explicit recalculation starts a fresh
  budget while preserving M039 atomic commit and cancellation semantics.
- Standalone `pylcl.evaluate` and `evaluate_sync` install no implicit limits.
- Budget context is task-safe in one event loop, resets in `finally`, and cannot
  leak across completed, failed, or cancelled evaluations.
- Public values and methods use complete English rST documentation; production
  and test submodules remain clear and implementation files stay below 200
  physical lines.

## TDD evidence

RED requires limit imports/constructor cases to fail because the API is absent.
GREEN requires all three budgets plus hierarchy, cache, recalculation, and
isolation cases. DONE requires the complete quality gate and synchronized
README/progress documentation.
