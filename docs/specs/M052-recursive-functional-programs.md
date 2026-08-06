# M052: recursive functional programs and exhaustive branch verification

## Goal

Verify recursion expressed through lexical fixed-point combinators while retaining
async-first calls, deterministic argument binding, and direct-re-entry protection. Verify
the complete production branch surface with meaningful public-behaviour tests.

## Behaviour

- Chained comparisons evaluate each operand once, from left to right, and compare
  adjacent values. Thus `10 > x > 2` is true for `x = 5` and false at either
  boundary.
- A fixed-point combinator recurs through freshly produced deferred closures;
  direct re-entry into the identical function value remains prohibited.
- A unary eta-expanded Y combinator and a variadic eta-expanded Z combinator are
  defined as distinct LCL expressions. Each independently defines factorial and
  Fibonacci under eager evaluation.
- Recursive quicksort is a separate Z-combinator case rather than part of either
  numeric-program assertion.
- Invalid bindings and host failures retain their existing structured errors.

## Module and test layout

- Function-call policy remains in `pylcl/lang/evaluator/functions.py`, mirrored
  by `tests/lang/evaluator/test_functions.py`.
- Comparison behaviour remains in `pylcl/lang/evaluator/operations.py`, mirrored
  by `tests/lang/evaluator/test_operations.py`.
- Remaining branch cases stay in the test module mirroring each production
  module. Production and test Python files remain below 200 physical lines.

## TDD matrix

- Sunny: `10 > x > 2` with `x = 5`, factorial 6, Fibonacci 10, and quicksort of
  duplicate and unordered integers.
- Rainy: comparison boundaries are false, invalid calls remain structured, and
  direct same-function re-entry retains its public recursion error.
- Composite-complex: define distinct Y and Z fixed-point combinators in LCL,
  derive factorial and Fibonacci independently from each, then define quicksort
  in a separate case and invoke every function without host recursion helpers.

## Completion evidence

Record the initial recursive-combinator compatibility result, focused result, exact
100% branch coverage, strict typing, Ruff, source/docstring/line gates, and full
test count in `progress.md` before marking this milestone DONE.
