# M043: module dependency graph queries and ordering

## Goal

Assemble static references into an immutable module graph with deterministic
forward/reverse queries, external-name reporting, and configurable topological
ordering with structured cycle diagnostics.

## Module and test layout

- `pylcl/runtime/dependencies.py` adds immutable public `DependencyEdge`.
- `pylcl/runtime/dependency_graph.py` owns immutable graph construction and
  forward/reverse/external queries.
- `pylcl/runtime/dependency_order.py` owns deterministic kind-filtered
  topological ordering and cycle-path discovery.
- Matching `tests/runtime/test_dependencies.py`, `test_dependency_graph.py`, and
  `test_dependency_order.py` mirror those production responsibilities.

## Contract

- `DependencyEdge(source, target, kind, span)` requires non-empty source/target
  names and a `DependencyKind`. Its span is the target occurrence span.
- `build_dependency_graph(module)` creates one vertex per definition in caller
  mapping order and one edge per static occurrence in definition then occurrence
  order. Repeated references remain repeated edges.
- `DependencyGraph.dependencies(source, kinds=None)` returns matching outgoing
  edges and raises source-aware-neutral `LclNameError` for an unknown source.
- `DependencyGraph.dependants(target, kinds=None)` returns matching incoming
  edges even when *target* is external. Kind filters are immutable sets; `None`
  means all kinds.
- `external_names` reports referenced non-definition names once, ordered by
  their first edge occurrence. Graph inputs and query results are immutable.
- `topological_order(graph, kinds={eager})` returns local definitions with every
  selected local dependency before its dependant. External targets do not
  affect ordering. Repeated edges retain evidence but do not corrupt ordering.
- Callers may include conditional, deferred, or dynamic kinds explicitly. An
  empty set returns definition order.
- A selected local cycle raises `LclCircularDependencyError` with a deterministic
  ordered path and the closing edge's occurrence span. Unselected cycles do not
  block ordering.
- Construction and ordering are pure and never evaluate definitions. Public
  values/functions use complete English rST docs; modules remain below 200
  physical lines with mirrored tests.

## TDD evidence

RED requires graph/edge public imports to fail. GREEN requires occurrence order,
queries, external names, filtering, deterministic ordering, duplicate edges,
and selected/unselected cycle cases. DONE requires the complete quality gate
and synchronized README/progress documentation.
