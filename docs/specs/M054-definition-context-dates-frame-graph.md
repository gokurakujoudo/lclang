# M054: definition context, date builtins, and Frame dependency graphs

## Goal

Expose the current definition name to trusted LCL expressions, add strict
calendar conversion helpers, and statically resolve dependencies through a
complete Frame hierarchy without evaluating definitions or host values.

## Module and test layout

- Definition context lives in `pylcl/lang/evaluator/definition_context.py`, mirrored by
  `tests/lang/evaluator/test_definition_context.py`.
- Calendar helpers live in `pylcl/stdlib/dates.py`; canonical hierarchy exposure
  remains in `pylcl/api.py` and is covered by mirrored stdlib/API tests.
- Frame graph values and construction live in
  `pylcl/runtime/dependency/frame/`, mirrored by
  `tests/runtime/dependency/frame/`.
- Runtime source files stay below 200 lines and every callable/value class uses
  complete English rST documentation.

## Definition-name contract

- `lhs()` is a synchronous, zero-argument host function in `LCL_ROOT`.
- While a Frame evaluates definition `name: expression`, `lhs()` returns
  `name` as `str`. Nested definition evaluation temporarily selects the nested
  owner and restores the dependant afterward; concurrent tasks remain isolated.
- A closure called as part of another definition sees that caller definition.
  Calling `lhs()` when no Frame definition is active raises a structured
  `LclEvaluationError`. Direct expression evaluation therefore cannot use it.
- Context setup and restoration cover success, ordinary failure, cancellation,
  recalculation, and dependency evaluation without leaking task state.

## Calendar builtin contract

- `parse_ymd(ymd: str) -> datetime.date` is exposed in `LCL_BUILTINS`. It
  accepts exactly eight ASCII decimal characters in `YYYYMMDD` order and uses
  Gregorian calendar validation. Non-strings raise `TypeError`; malformed or
  impossible dates raise `ValueError` at the helper boundary and the established
  structured evaluation wrapper from LCL.
- `to_ymd(d: datetime.date) -> str` is exposed in `LCL_BUILTINS`. It accepts
  `date` instances and returns zero-padded `YYYYMMDD`; other values raise
  `TypeError`.
- Neither helper reads ambient state, performs I/O, or depends on locale/timezone.

## Frame graph contract

- `build_dependency_graph` retains its exact Module behavior and additionally
  accepts a `Frame`, returning an immutable `FrameDependencyGraph`.
- `FrameDependencyBinding(frame_path, name, kind)` identifies a selectable
  definition or host value. `frame_path` starts at the analyzed Frame and grows
  toward its owner, so shadowed equal names remain distinct.
- The graph snapshots every hierarchy definition and every selectable host
  value in child-to-parent order. A same-Frame definition masks its same-name
  value. Construction reads syntax and binding names only: it never resolves an
  awaitable, calls a host value, evaluates an AST, populates a cache, or changes
  a dependency trace, and it remains valid for closed Frames.
- Each `FrameDependencyEdge` retains the source binding, requested target name,
  static kind/span, exact Frame IDs searched from the source owner, and either
  the selected definition/value binding or `None` when unresolved.
- Parent-owned definitions resolve their own dependencies starting at their
  owner, matching evaluation semantics rather than restarting at the analyzed
  child. `external_names` includes only unresolved references; resolved host
  values are graph terminals, not external names.
- Frame dependency/dependant queries preserve occurrence order and accept the
  same immutable kind filters as Module graphs. Cyclic parent object graphs and
  unsupported builder inputs fail with `ValueError`/`TypeError` before a graph
  is published.

## Configuration integration

- `FrameFactory` may retain an optional borrowed default parent. A non-`None`
  call parent overrides it; `with_preset` preserves it.
- `Config.frame_factory(*, preset=None, parent=None, limits=None)` uses the
  canonical `LCL_IMPORTS` parent when no parent is supplied. This makes root and
  builtin functions available to loaded configuration while direct low-level
  factories remain hierarchy-free. `evaluate_config` shares the same policy.

## TDD matrix

- Sunny: evaluate `k: {"name": lhs()}`, leap-day parse/format round trips, and
  a Frame graph whose definition and value references resolve through the exact
  hierarchy paths.
- Rainy: reject out-of-context `lhs`, malformed/impossible dates, invalid helper
  types, unsupported graph inputs, and parent hierarchy cycles.
- Composite-complex: load a config using `lhs`, `parse_ymd`, and `to_ymd`; prove
  nested and concurrent definitions retain distinct names; build its full Frame
  graph before evaluation and prove values, shadowing, unresolved names, caches,
  and dynamic traces remain untouched.

## Completion evidence

Record focused RED/GREEN commands, full test count and coverage, strict mypy,
Ruff, source/docstring/line policy, documentation links, and `git diff --check`
in `progress.md` before marking the milestone verified.
