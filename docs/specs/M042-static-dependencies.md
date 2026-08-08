# M042: dependency references and scope-aware static analysis

## Goal

Extract every free variable occurrence from semantic AST while classifying when
evaluation can demand it and respecting every language binding scope.

## Module and test layout

- `pylcl/runtime/dependency/model.py` owns public immutable dependency kinds and
  reference values.
- `pylcl/runtime/dependency/analysis.py` owns pure scope-aware AST traversal.
- `tests/runtime/dependency/test_model.py` mirrors value validation and stable kinds.
- `tests/runtime/dependency/test_analysis.py` mirrors eager, conditional,
  deferred, binding, comprehension, and control-form traversal.

## Contract

- `DependencyKind` has stable string values `eager`, `conditional`, `deferred`,
  and `dynamic`. M042 static analysis emits the first three; runtime tracing
  begins emitting `dynamic` in M044.
- `DependencyReference(name, kind, span)` requires a non-empty `VarName` and
  identifies one syntactic free-name occurrence. Occurrences are not deduplicated
  because their spans and control paths remain diagnostic evidence.
- `analyze_dependencies(node)` is pure and returns references in runtime
  evaluation order where that differs from AST source-child order.
- Ordinary operands, call parts, displays, f-string fields, raise values, and
  context-manager acquisition/body expressions are eager.
- Later Boolean operands, coalesce fallback, conditional value branches, later
  comparison operands, assertion messages, and try handlers are conditional.
  Try finalization remains eager.
- Function defaults retain their surrounding classification. Function bodies
  are deferred, and parameter names are bound only inside the body.
- A materialized comprehension's first iterable retains the surrounding kind;
  later iterables, filters, and output are conditional. Clause targets bind only
  after their iterable and remain bound for later clauses/output.
- Every dependency of a generator expression is deferred because iteration is
  lazy in the evaluator.
- `except ... as`, `with ... as`, function parameters, and comprehension targets
  suppress references only within their actual lexical scope. Attribute names
  and keyword labels are metadata, never dependencies.
- Classification only weakens along nested control: deferred dominates
  conditional, which dominates eager. Static traversal never executes user code.
- Public values/functions use complete English rST documentation and all source
  and mirrored test modules remain below 200 lines.

## TDD evidence

RED requires public imports to fail because dependency modules are absent.
GREEN requires all value, ordering, control, laziness, and scope cases. DONE
requires the complete quality gate and synchronized README/progress documents.
