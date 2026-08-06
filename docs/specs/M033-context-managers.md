# M033: sync/async context managers and cleanup

## Goal

Evaluate `with` expressions with Python-compatible acquisition, binding,
suppression, unwinding, and cancellation behaviour across synchronous and
asynchronous context-manager protocols.

## Module and test layout

- `pylcl/lang/evaluator/contexts.py` owns context acquisition, target binding,
  body evaluation, and reverse-order unwinding.
- `tests/lang/evaluator/test_contexts.py` mirrors synchronous, asynchronous,
  multi-item, failure, suppression, and cancellation behaviour.
- The central evaluator dispatches `LclWith` nodes into the context module and
  retains the M032 source-aware failure boundary.

## Contract

- Context expressions are evaluated and entered from left to right. Every
  optional `as` target is bound only in a nested body scope; the caller resolver
  is unchanged. A later context expression can resolve earlier bindings.
- A value supporting `__aenter__` and `__aexit__` uses the asynchronous
  protocol. Otherwise it uses `__enter__` and `__exit__`. Missing or invalid
  protocol methods fail through the ordinary source-aware evaluation boundary.
- Entry and exit results are auto-awaited, including awaitables returned from
  nominally synchronous protocol methods.
- Successfully entered managers exit exactly once in right-to-left order. If a
  later acquisition fails, all earlier managers still unwind.
- On normal completion each exit receives `(None, None, None)` and the with
  expression returns its body result.
- On failure each exit receives the current exception type, value, and
  traceback. A truthy exit result suppresses that failure for outer exits and
  makes the with expression return `None`; a falsey result preserves it.
- If an exit raises, that new failure replaces the pending result or failure
  while preserving normal Python exception chaining.
- Direct `BaseException` values, including `asyncio.CancelledError`, are never
  converted to `LclEvaluationError`, but successfully entered managers still
  unwind and receive the cancellation details.
- Complete English rST documentation and the 200-line source limit remain
  mandatory.

## TDD evidence

RED requires focused with-expression cases to fail as unsupported nodes. GREEN
requires all acquisition, binding, suppression, failure, and cancellation
cases. DONE requires the complete quality gate and synchronized README/progress
documentation.
