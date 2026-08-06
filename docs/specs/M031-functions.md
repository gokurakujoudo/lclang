# M031: function values, binding, and lexical closures

## Goal

Turn function AST forms into async callable values with deterministic default
evaluation, Python-like argument binding, lexical name resolution, and explicit
non-recursion policy.

## Module and test layout

- `pylcl/lang/evaluator/functions.py` owns function creation, bound defaults,
  invocation, argument validation, local scope construction, and recursion
  detection.
- `tests/lang/evaluator/test_functions.py` mirrors creation, every parameter
  kind, defaults, closures, failures, concurrency, and recursion.
- The central evaluator delegates only `LclFunction`; ordinary call evaluation
  invokes the resulting value through M030.

## Contract

- Default expressions evaluate left-to-right exactly once when the function
  value is created, in the defining resolver. Missing required parameters fail
  only when the function is called.
- Positional parameters accept positional or named arguments. Keyword-only,
  variadic positional, and variadic keyword parameters follow their AST kinds.
  Duplicate, missing, excess, or unexpected arguments raise `TypeError` before
  body evaluation.
- Invocation overlays bound locals on the captured defining resolver. Call-site
  resolver names never replace closure names; mutable resolver implementations
  may expose their own later updates by design.
- Function calls are async and their bodies use the ordinary evaluator, so
  deferred values and results are fully resolved.
- Concurrent calls in separate tasks are supported. Direct or indirect
  re-entry into the same function value in one task raises source-aware
  `LclEvaluationError`; recursion is not part of LCL V1.
- Function values expose a documented callable type but no Python code object,
  `eval`, `exec`, or AST compilation.
- Complete English rST documentation and the 200-line module limit remain
  enforced.

## TDD evidence

RED requires the function suite to fail with unsupported-node diagnostics.
GREEN requires binding, closure, concurrency, and recursion cases. DONE requires
the complete quality gate and synchronized documentation.
