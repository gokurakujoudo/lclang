# M021: comprehensions and unpacking

## Goal

Represent and parse generator, list, set, and dictionary comprehensions,
including PEP 798-style iterable and mapping unpack heads.

## Module and test layout

- `pylcl/ast/comprehensions.py` and `tests/ast/test_comprehensions.py` own
  immutable clause and comprehension node values.
- `pylcl/lang/parser/comprehensions.py` and its mirrored test own target parsing,
  repeated `for`/`if` clauses, closing delimiters, and node selection.
- `displays.py` detects `for` after the first display head and delegates.
- `logical.py` exposes a non-conditional expression mode for unambiguous
  iterable and filter boundaries.

## Contract

- `(value for name in iterable)`, list, set, and dict counterparts produce
  distinct immutable nodes.
- Each clause has one non-empty name target, one iterable, and zero or more
  filters. Multiple `for` clauses and multiple `if` filters preserve source
  order.
- List and set comprehensions accept ordinary or `*` heads. Dict
  comprehensions accept key/value or `**` heads, matching PEP 798 syntax.
- Ordinary collection entries cannot follow a comprehension clause.
- Iterable and filter expressions use the non-conditional logical layer;
  explicit grouping still permits a conditional expression.
- Async comprehension spelling is outside LCL V1; iteration itself remains
  async-capable in the evaluator.
- Missing target, `in`, iterable, condition, or closing delimiter; invalid head
  type; and mixed entry/comprehension syntax raise source-aware syntax errors.
- `children()` order is head, then clauses; each clause is target, iterable,
  then filters. Public docstrings satisfy M007.

## TDD evidence

RED must fail because both comprehension modules are absent and `for` is
rejected by display parsing. GREEN requires both mirrored suites and parser
regressions. DONE requires the complete quality gate and documentation sync.
