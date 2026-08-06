# M020: logical and conditional parser layer

## Goal

Add comparison chains, Boolean short-circuit expressions, null coalescing, and
conditional expressions above the arithmetic Pratt core.

## Module and test layout

- `pylcl/lang/parser/logical.py` owns the low-precedence recursive-descent layer.
- `tests/lang/parser/test_logical.py` mirrors that module.
- `pratt.py` supplies arithmetic operands and delegates nested full expressions
  without duplicating logical rules.

## Contract

- Ordered, equality, membership, negated membership, identity, and negated
  identity operators build one `LclCompare` chain and preserve operand order.
- `not` binds looser than comparisons but tighter than `and`; repeated `and` and
  `or` operands flatten into `LclBoolean` nodes with `and` tighter than `or`.
- `??` binds looser than `or`, is right-associative, and only represents null
  fallback; truthiness is irrelevant to its syntax and later semantics.
- `when_true if condition else when_false` binds loosest and is
  right-associative through its false branch.
- Logical expressions work everywhere a nested expression is accepted:
  grouping, displays, indices, slices, and call arguments.
- Incomplete two-word comparisons, missing operands/`else`, and repeated stray
  operators raise source-aware `LclSyntaxError`.
- Result spans cover the full expression and public docstrings satisfy M007.

## TDD evidence

RED must fail because the logical parser module is absent and all low-precedence
tokens remain trailing input. GREEN requires the mirrored logical suite and
existing parser regression tests. DONE requires the complete quality gate and
documentation synchronization.
