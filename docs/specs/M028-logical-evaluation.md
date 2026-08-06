# M028: short-circuit logical evaluation

## Goal

Evaluate truth-based and null-based control expressions without eagerly
visiting skipped branches, while preserving Python-style operand results.

## Module and test layout

- `pylcl/lang/evaluator/logical.py` owns logical `not`, flattened Boolean
  nodes, conditionals, and null coalescing.
- `tests/lang/evaluator/test_logical.py` mirrors value semantics, evaluation
  order, skipped failures, and deferred conditions.
- Central dispatch only recognizes and delegates the logical node family.

## Contract

- `not` returns a `bool` using ordinary truth testing after its operand is fully
  awaited.
- `and` evaluates left-to-right and returns the first falsey operand, otherwise
  the final operand. `or` returns the first truthy operand, otherwise the final
  operand. Skipped operands are never resolved.
- A conditional evaluates its condition first, then exactly one value branch.
  Its source-order AST child order does not determine runtime order.
- Coalescing evaluates its right side only when the resolved left value is
  exactly `None`; false, zero, empty strings, and empty collections are retained.
- Truth-testing exceptions from trusted values propagate unchanged until the
  M032 wrapping boundary.
- All public documentation remains complete English rST and production files
  remain below 200 lines.

## TDD evidence

RED requires logical tests to fail with unsupported-node diagnostics. GREEN
requires value and short-circuit cases. DONE requires the complete quality gate
and synchronized README and progress status.
