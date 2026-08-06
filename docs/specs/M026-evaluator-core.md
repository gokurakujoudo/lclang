# M026: async evaluator core and resolver boundary

## Goal

Establish the small async-first execution boundary used by every later AST
handler and by runtime Frames, with constant/name evaluation, automatic
awaitable resolution, and the single supported synchronous convenience API.

## Module and test layout

- `pylcl/lang/evaluator/context.py` owns the resolver protocol and mapping
  adapter; `tests/lang/evaluator/test_context.py` mirrors lookup behaviour.
- `pylcl/lang/evaluator/awaitables.py` owns automatic awaitable resolution and
  its mirror covers immediate and deferred values.
- `pylcl/lang/evaluator/evaluator.py` owns public dispatch, `evaluate`, and
  `evaluate_sync`; its mirror covers constants, names, unsupported nodes, and
  event-loop boundaries.
- Package `__init__.py` files contain exports only.

## Contract

- `Resolver` is an async structural protocol resolving a `VarName`. A mapping
  adapter accepts string-compatible keys without copying caller values.
- Missing names raise `LclNameError` with the originating AST span. Exceptions
  raised by user resolvers propagate unchanged.
- Every value produced by a node handler is passed through automatic awaitable
  resolution before it is returned. Non-awaitable values incur no scheduling.
- `evaluate` is the public async API. M026 supports constants and names;
  unsupported semantic nodes raise source-aware `LclEvaluationError`.
- `evaluate_sync` uses a private event loop only when no event loop is running
  in the current thread. Inside a running loop it raises `RuntimeError` and
  callers must await `evaluate`.
- Empty resolver input is valid. Evaluation mutates neither the AST nor caller
  mappings.
- All public docstrings use complete English rST fields and every source module
  remains below 200 lines.

## TDD evidence

RED requires mirrored tests to fail because the evaluator package and public
entry points do not exist. GREEN covers every M026 path. DONE requires the full
quality gate and synchronized documentation.
