# M056 - Frame inspection and nested runtime package

Status: VERIFIED

## Goal

Make direct `Frame` construction ergonomic, give users a side-effect-free tree
for understanding one variable, and group the complete Frame subsystem beneath
`pylcl.runtime.frame` without changing the established runtime import surface.

## Public contract

- `Frame(module, frame_id=None, ...)` accepts `FrameId`, ordinary `str`, or
  `None`. A string is normalized through `FrameId`; `None` becomes
  `FrameId(f"frame-{module.name}")`. The effective identifier must be non-empty,
  and every other runtime type retains its existing validation.
- `FrameFactory.create()` delegates the same identifier normalization to
  `Frame`, so factory and direct construction have one defaulting rule.
- `Frame.inspect_variable(var_name)` returns a `VariableInspectionTree` and
  never evaluates definitions, awaits host values, creates tasks, mutates
  caches, or publishes dependency traces. Empty names are rejected and closing
  or closed Frames retain the existing lifecycle rejection.
- `VariableInspectionStatus` is a string enumeration with the public values
  `Cached`, `NotEvaluated`, `ExternalProvided`, and the M095 addition
  `NativeProvided`.
- `VariableInspectionTree` exposes `var_name`, `status`, `definition`,
  `definition_path`, `defined_at`, `current_value`, `current_exception`, and
  `dependencies`. Paths and dependencies are ordinary detached lists.
- A selected definition is `Cached` when either its successful result or its
  ordinary failure is cached, and is otherwise `NotEvaluated`. A selected host
  value is `ExternalProvided`, has no definition, exposes the current unawaited
  host object as `current_value`, and has no dependencies.
- M095 refines canonical `LCL_ROOT`/`LCL_BUILTINS` host values to
  `NativeProvided`; ordinary application, preset, and CLI host values remain
  `ExternalProvided`.
- A successful cache sets `current_value`; a cached failure sets
  `current_exception`. The unused member is `None`. In-flight work without a
  committed snapshot remains `NotEvaluated` and is neither joined nor exposed.

## Tree lookup semantics

- Root lookup starts at the inspected Frame. Every definition dependency starts
  lookup from the Frame that owns that definition, matching evaluator lexical
  ownership rather than restarting at the original child.
- `definition_path` lists every searched `FrameId` from that lookup origin
  through the selected owner, inclusive. For an unresolved name it lists the
  complete attempted path, `defined_at` is the lookup-origin Frame,
  `definition` is `None`, status is `NotEvaluated`, and `current_exception` is
  a structured `LclNameError`. This keeps missing inputs inspectable despite
  the intentionally compact three-state status model.
- Static, scope-aware dependency analysis supplies children in source order.
  Immediate children are unique by variable name at their parent, retaining the
  first occurrence. The same variable on separate branches remains present;
  the result is a tree, never a globally deduplicated graph.
- If a `(Frame identity, variable name)` pair repeats on its current ancestor
  branch, the repeated node is emitted once as a leaf. Other branches still
  expand that same pair independently. This path-local truncation guarantees a
  finite representation without inventing cache state.
- Definitions mask host values in the same Frame. A nearer host value masks an
  ancestor definition. Parent object cycles remain structural errors.

## Presentation

- `repr(tree)` uses the source-oriented
  `name@frame/path: [definition ](Status) typed-payload` grammar specified by
  M058, with canonical AST and evaluated LCL function value payloads added by
  M098. It does not recursively render Frames or child trees.
- `tree.to_lines(depth=0, prefix="- ")` returns a detached list of markdown-style
  lines. Every level adds two spaces before the caller prefix, then the one-line
  representation. `depth` must be non-negative and `prefix` must be a string.

## Package layout

- The central class and all Frame-only mixins, cache ownership, lookup,
  dependency snapshots, flights, recalculation, limits, factory, and inspection
  implementation move under `pylcl.runtime.frame`.
- `pylcl.runtime` continues to export `Frame`, `FrameFactory`, and
  `EvaluationLimits`, and additionally exports `VariableInspectionStatus` and
  `VariableInspectionTree`. Existing root `pylcl.Frame` identity is unchanged.
- Old peer module paths are removed. Production imports and mirrored tests use
  the nested package, and the exhaustive filename audit records every move.

## Acceptance

- Sunny tests cover omitted/string/nominal identifiers, uncached and cached
  definitions, cached failures, external values, lexical parent ownership,
  first-seen dependency order, duplicate branches, and markdown rendering.
- Rainy tests cover empty/wrong identifiers, empty inspection names, missing
  dependencies, parent cycles, closed Frames, and rendering argument errors.
- A composite test inspects a multi-Frame expression with cached, uncached,
  external, repeated, failing, and cyclic branches; before/after cache and trace
  snapshots prove inspection has no evaluation effects.
- Documentation adds a practical inspection section to the runtime tutorial and
  links it from dependency analytics. The module-layout guide and exhaustive
  filename audit reflect the nested package atomically.
- Focused and full pytest, branch coverage, strict mypy, Ruff, source policy for
  touched modules, documentation checks, and `git diff --check` pass before the
  milestone is marked VERIFIED.
