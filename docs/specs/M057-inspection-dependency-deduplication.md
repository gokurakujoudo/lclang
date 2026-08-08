# M057 - Inspection dependency deduplication

Status: VERIFIED

## Goal

Make `Frame.inspect_variable()` concise by showing each directly referenced
variable once beneath a definition, without turning the overall result into a
graph or changing dependency analytics elsewhere.

## Contract

- For each definition node, inspection consumes static dependency references in
  source order and retains only the first occurrence of each `VarName`.
- Deduplication is local to one parent's immediate children. For
  `x: a + b + b`, `x.dependencies` is `[a, b]` in that order.
- The same variable may still appear under separate branches. If `x` depends on
  `left` and `right`, and both depend on `shared`, both branch-local `shared`
  nodes remain present and expand independently.
- A variable used with different dependency kinds or source spans still has one
  direct inspection child; the first source occurrence determines its position.
  `VariableInspectionTree` does not expose edge kind or span.
- Cycle truncation remains path-local and occurs after per-parent name
  deduplication. Missing names, lookup paths, owners, cache status, values,
  exceptions, and zero-evaluation behavior are unchanged.
- `analyze_dependencies`, Module/Frame dependency graphs, runtime traces, and
  dependency snapshots remain occurrence-preserving. This refinement applies
  only to the explanatory inspection tree.

## Acceptance

- Sunny coverage proves `a + b + b` yields direct children `a, b` in first-seen
  order and markdown output contains one direct `b` line.
- Rainy coverage proves repeated missing and external names are also collapsed
  without evaluating, awaiting, or losing their diagnostic/value evidence.
- Composite coverage proves a shared dependency remains duplicated across two
  different branches while repeated occurrences inside either branch collapse.
- Runtime and dependency tutorials explain the tree/graph distinction and use
  deduplicated expected results.
- Focused/full pytest, branch coverage, strict mypy, Ruff, documentation checks,
  isolated source policy, and `git diff --check` pass before VERIFIED.
