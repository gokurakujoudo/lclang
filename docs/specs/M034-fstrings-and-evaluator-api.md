# M034: semantic f-strings and evaluator API audit

## Goal

Complete V1 expression evaluation with deterministic formatted strings, then
verify the async-first public boundary and recursive auto-await guarantees for
every evaluator family.

## Module and test layout

- `pylcl/lang/evaluator/fstrings.py` owns formatted-string part evaluation,
  conversion, format-spec recursion, and concatenation.
- `tests/lang/evaluator/test_fstrings.py` mirrors literal, conversion,
  formatting, nested-spec, evaluation-order, awaitable, and failure behaviour.
- `tests/lang/evaluator/test_dispatch.py` and `tests/test_public_api.py` retain
  the async/sync boundary and root-package export audit.

## Contract

- Literal f-string parts are appended unchanged. Expression parts are evaluated
  exactly once, from left to right, using the active resolver.
- No conversion uses the value directly; `!s`, `!r`, and `!a` apply `str`,
  `repr`, and `ascii` respectively before formatting.
- An absent format spec uses ordinary string conversion after any explicit
  conversion. A present spec is itself evaluated as a semantic formatted string
  and supplied to Python's `format(value, spec)` protocol.
- A debug field prefixes the canonical expression source and `=`. With neither
  explicit conversion nor format spec it defaults to `repr`; with a format spec
  it follows ordinary formatting, matching Python's debug-field behaviour.
- Expression and nested format-spec results are recursively auto-awaited by the
  shared evaluator boundary.
- Application conversion and formatting failures use the M032 nearest-node
  `LclEvaluationError` boundary with the original exception as cause.
- `pylcl.evaluate` remains async-first, `pylcl.evaluate_sync` remains the sole
  synchronous convenience boundary, and both retain complete English rST
  contracts and stable root-package exports.
- Once complete, every semantic AST family planned for V1 is evaluable; the
  generic unsupported-node diagnostic remains defensive for custom subclasses.
- Complete English rST documentation, strict typing, and the 200-line source
  limit remain mandatory.

## TDD evidence

RED requires focused formatted-string cases to fail at the unsupported-node
boundary. GREEN requires all part, conversion, spec, order, awaitable, and error
cases. DONE requires the complete quality gate and synchronized README/progress
documentation.
