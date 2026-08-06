# M044: runtime dependency tracing and edge reconciliation

## Goal

Record the free-name occurrences that evaluation actually resolves, including
lookups performed later by lexical closures, and compare that evidence with a
module's static dependency edges without coupling the mechanism to `Frame`.

## Module and test layout

- `pylcl/runtime/dependency_tracing.py` owns a per-definition trace and a
  resolver decorator that records before delegating lookup.
- `pylcl/runtime/dependency_reconciliation.py` owns the immutable comparison
  result and pure reconciliation function.
- `tests/runtime/test_dependency_tracing.py` and
  `tests/runtime/test_dependency_reconciliation.py` mirror those production
  responsibilities.

`Frame` ownership, published snapshots, and atomic recalculation replacement
belong to M045 rather than this milestone.

## Contract

- `DependencyTrace(source)` requires a non-empty definition name. Its
  `record(target, span)` method emits a `DependencyEdge` of kind `dynamic`.
- A trace preserves first-observation order and keeps distinct source spans,
  while repeated resolution of the exact same source/target/span occurrence is
  idempotent. This bounds traces for repeated comprehension or generator
  iteration without losing syntactic evidence.
- The `edges` property returns an immutable point-in-time tuple. Previously
  returned tuples never change when later observations arrive.
- `TracingResolver(trace, parent)` records a requested free name before
  delegating to its parent resolver. Missing and failing lookups therefore
  remain observable, while the parent's value and exception semantics pass
  through unchanged.
- The resolver retains the trace by reference. When captured by an LCL function
  or lazy generator, later lookup continues to extend the defining source's
  trace. Scoped local bindings are not recorded because `ScopedResolver`
  resolves them before delegating to the captured tracing resolver.
- Distinct traces share no mutable state and need no global context. Recording
  performs no await and is safe for cooperative tasks in one event loop.
- `reconcile_dependency_edges(static_edges, dynamic_edges)` is pure and matches
  occurrences by source, target, and exact span. Static classification is not
  overwritten by runtime classification.
- `DependencyReconciliation.confirmed` contains statically predicted
  occurrences observed at runtime in static order; `inactive` contains the
  remaining static occurrences in static order; `unexpected` contains dynamic
  occurrences with no static match in observation order.
- Reconciliation validates that its static input contains no dynamic edges and
  its dynamic input contains only dynamic edges. Empty inputs are valid.
- Public values, properties, methods, and functions use complete English rST
  documentation. Production and mirrored test modules remain below 200
  physical lines.

## TDD evidence

RED requires imports of tracing and reconciliation APIs to fail. GREEN requires
validation, order, idempotence, span distinction, success/failure delegation,
closure/local-scope behaviour, snapshot immutability, exact reconciliation,
input validation, and empty inputs. DONE requires the complete quality gate and
synchronized bilingual README/progress documentation.
