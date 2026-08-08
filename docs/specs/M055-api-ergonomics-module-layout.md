# M055: evaluation ergonomics and Python module layout

## Goal

Make definition ownership lexical inside LCL closures, remove boilerplate from
the synchronous evaluator and Frame factories, document dependency analytics,
and give every Python file a responsibility-revealing audited location.

## Definition context

- `lhs()` remains available only while evaluating a named Frame definition.
- Argument expressions use the caller definition. A function body uses the
  definition in which that function value was created. For definitions
  `x: def (a): f"{a}-{lhs()}"` and `y: x(lhs())`, `y` evaluates to `"y-x"`.
- Nested dependency evaluation temporarily selects its own owner, then restores
  the caller. Function values capture an optional owner alongside their lexical
  resolver. Standalone functions created without a Frame owner do not invent
  one. Context remains task-local and is restored on success, failure, and
  cancellation.

## Synchronous evaluation

- `evaluate_sync(node_or_source, resolver=None)` accepts either an immutable
  `LclAstNode` or LCL source text.
- Source text is parsed with `parse_expression` and then follows the existing
  private-event-loop evaluation path. Syntax and evaluation errors retain their
  existing structured types.
- Passing source text is the preferred synchronous usage in tutorials and API
  documentation. Explicit parsing remains supported when callers need the AST,
  custom origins, printing, or dependency inspection.
- Async-first `evaluate` remains AST-only and unchanged.

## FrameFactory identifiers

- `FrameFactory.create(frame_id=None, *, ...)` accepts an omitted identifier.
- Omission deterministically selects `FrameId(f"frame-{factory.module.name}")`.
- Explicit non-empty identifiers retain exact existing behavior; an explicitly
  empty `FrameId` remains invalid.

## Dependency analytics tutorial

- `docs/tutorials/dependency-analytics.md` explains static references, Module
  graphs, Frame-qualified lookup, host-value terminals, eager/conditional/
  deferred kinds, runtime traces, snapshots, reconciliation, ordering, and the
  zero-evaluation guarantee.
- Every code sample states its expected result and explains which question the
  output answers. The tutorial index and root READMEs link the guide.

## Python filename audit

- Review every production, maintenance-script, and test filename against its
  module docstring and top-level declarations. Record each decision in
  `docs/architecture/python-file-name-audit.md`.
- Keep accurate family names even when plural; renaming is not a goal by itself.
  Test modules continue to mirror production subsystem paths.
- Move definition context from `runtime` to `lang/evaluator`, because LCL
  closures must capture it without creating a language-to-runtime dependency.
- Rename the redundant central modules `lang/evaluator/evaluator.py` and
  `lang/printer/printer.py` to `dispatch.py`. Split the synchronous boundary
  into evaluator `sync.py`, and split argument binding into
  `function_arguments.py`, keeping touched production files below 200 lines.
- Group static, dynamic, and Frame-qualified analytics into the nested
  `runtime/dependency/` package. Frame graph model, resolution, and construction
  live one level deeper under `runtime/dependency/frame/`. Mirror both levels
  under `tests/runtime/dependency/`.
- Rename `config/merge.py` to `config/result.py`; the file owns the expanded
  immutable `Config` result and runtime bridge, not a merge operation.
- Package-root re-exports remain stable. Internal module paths and architecture
  documentation are updated atomically, with no compatibility aliases for
  undocumented internal locations.
- Every basename contains at most five underscore-delimited words.

## TDD matrix

- Sunny: evaluate the lexical nested-`lhs` example, call `evaluate_sync` with
  source and a resolver, and create a default-ID Frame.
- Rainy: preserve out-of-context `lhs`, structured invalid source, running-loop,
  explicit empty Frame ID, and wrong input failures.
- Composite-complex: build a default-ID Frame whose closure uses `lhs`, inspect
  its Frame graph before evaluation, evaluate through string convenience, and
  prove cache/trace state changes only at the explicit evaluation boundary.
- Structural: assert audited module paths exist, retired paths do not, imports
  and documentation contain no stale references, mirrored tests follow moved
  production modules, and all basenames satisfy the five-word ceiling.

## Completion evidence

Record RED/GREEN commands, filename-audit checks, executable tutorial results,
full test count and branch coverage, strict mypy, Ruff, source/docstring/line
policy, and `git diff --check` in `progress.md` before verification.
