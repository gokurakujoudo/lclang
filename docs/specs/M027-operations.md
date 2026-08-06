# M027: unary, binary, and comparison evaluation

## Goal

Evaluate ordinary operator nodes with Python-compatible trusted-value semantics,
strict left-to-right operand order, automatic awaiting, and one-time comparison
chain operands.

## Module and test layout

- `pylcl/lang/evaluator/operations.py` owns unary, arithmetic, bitwise,
  membership, identity, and ordered comparison dispatch.
- `tests/lang/evaluator/test_operations.py` mirrors all operator families,
  evaluation order, chain short-circuiting, and awaitable operands.
- The central evaluator only recognizes the family and delegates recursively;
  it does not duplicate operator tables.

## Contract

- Unary `+`, `-`, and `~` use their Python data-model operations. Logical `not`
  is deferred to M028 because it belongs to short-circuit truth semantics.
- Every binary operator in `BinaryOperator` uses its corresponding Python
  operation. The left operand completes before right evaluation begins.
- Comparison chains evaluate each operand at most once, left-to-right, and stop
  immediately after the first false comparison.
- Membership and identity preserve Python `in`, `not in`, `is`, and `is not`
  behaviour for trusted application values.
- Resolver-produced awaitables are fully resolved before each operation.
- User data-model exceptions propagate unchanged in M027; M032 later adds the
  public evaluation-failure wrapping boundary without changing operator order.
- Source modules remain below 200 lines and public docstrings retain complete
  English rST documentation.

## TDD evidence

RED requires operation tests to fail with M026's unsupported-node diagnostic.
GREEN requires all operator and ordering cases. DONE requires the complete
quality gate and documentation synchronization.
