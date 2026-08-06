# M029: collection and comprehension evaluation

## Goal

Evaluate displays, unpacking, generators, and comprehensions over synchronous or
asynchronous inputs with isolated loop-target bindings and deterministic order.

## Module and test layout

- `pylcl/lang/evaluator/displays.py` owns tuple/list/set/dict construction and
  explicit `*`/`**` expansion; its mirror covers order and protocol failures.
- `pylcl/lang/evaluator/iteration.py` adapts sync and async iterables to one
  internal async stream; its mirror covers both protocols and invalid values.
- `pylcl/lang/evaluator/comprehensions.py` owns clauses, target scopes,
  conditions, PEP 798 unpacking, and generator results; its mirror covers nested
  clauses, skipped heads, async sources, and scope isolation.
- `ScopedResolver` in `context.py` overlays local bindings without mutating its
  parent and is covered by the context mirror.

## Contract

- Display elements and dictionary entries evaluate left-to-right. Sequence
  stars consume iterable values; dictionary stars require mapping-compatible
  values and preserve later-key overwrite semantics.
- Comprehension clauses nest left-to-right. Each target binding is visible to
  its iterable's later clauses, conditions, and head, but never mutates the
  caller resolver or mapping.
- Every iterable may implement either `__iter__` or `__aiter__`. Async iteration
  is consumed without blocking; invalid inputs raise their ordinary `TypeError`.
- Conditions are evaluated in source order and short-circuit the remaining
  conditions and head for that item.
- List, set, and dict comprehensions materialize eagerly. Generator expressions
  return an async iterator and perform no clause or head evaluation until it is
  consumed.
- PEP 798 starred comprehension heads expand iterables; dictionary double-star
  heads expand mappings in iteration order.
- Public docstrings remain complete English rST and source files stay below 200
  lines.

## TDD evidence

RED requires the three mirrored suites to fail on unsupported collection nodes.
GREEN requires display, scope, sync/async iteration, and lazy-generator cases.
DONE requires the complete quality gate and synchronized documentation.
