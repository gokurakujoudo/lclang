# M032: raise, assert, try, and evaluation failure boundaries

## Goal

Provide source-aware deliberate failures, assertions, typed recovery, guaranteed
finalization, and one consistent public wrapper for application-protocol errors.

## Module and test layout

- `pylcl/lang/evaluator/errors.py` owns raise/assert/try evaluation, handler
  matching, handler bindings, and failure wrapping helpers.
- `tests/lang/evaluator/test_errors.py` mirrors deliberate errors, lazy messages,
  typed/bare handlers, causes, unmatched failures, finalization, and cancellation.
- Existing evaluator-family tests are updated where M032 intentionally changes
  raw application exceptions into structured public failures.

## Contract

- `raise(value)` raises `LclEvaluationError` at the raise-node span. Its message
  is `str(value)` or a stable fallback; a `BaseException` value becomes its
  `__cause__`.
- `assert(condition, message)` returns the truthy condition value. On a falsey
  condition it lazily evaluates the optional message and raises a source-aware
  `LclEvaluationError`.
- Every ordinary `Exception` escaping trusted resolver, operator, descriptor,
  iteration, binding, or call protocols is wrapped once at the nearest AST node
  in `LclEvaluationError`, preserving the original as `__cause__`. Existing
  `LclError` values pass unchanged.
- Try handlers are tested in source order. Bare handlers match any `Exception`;
  typed handlers use `isinstance` against the public error or any cause in its
  chain. Invalid matcher values fail normally through the wrapping boundary.
- An `as` target binds the public caught error only inside that handler scope.
  The caller resolver is unchanged.
- `finally` always runs after body or handler. Its failure replaces the pending
  result/failure according to ordinary Python cleanup semantics.
- `asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit`, and other direct
  `BaseException` subclasses are neither wrapped nor caught by LCL handlers;
  finalization still runs.
- Complete English rST documentation and the 200-line source limit remain
  mandatory.

## TDD evidence

RED requires error/control cases to fail as unsupported nodes and existing raw-
failure tests to demonstrate the pre-M032 boundary. GREEN requires all recovery,
cause, finalization, and cancellation cases. DONE requires the complete quality
gate and documentation synchronization.
