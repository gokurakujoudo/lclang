# lclang feature inventory

Version is the stable release of `lclang` for Python 3.14 and newer. The
package is pure Python, MIT licensed, fully typed, and has no third-party
runtime dependencies.

## Language

- Unicode lexer with source spans, comments, literals, bytes, raw strings, and
  semantic f-strings.
- Immutable AST, versioned parser, structured syntax diagnostics, and
  precedence-aware canonical source rendering.
- Arithmetic, comparisons, boolean short-circuiting, conditionals, null
  coalescing, safe attributes, calls, subscripts, slices, and unpacking.
- Tuple, list, set, and dictionary displays; generator, list, set, and dictionary
  comprehensions; sync and async iteration.
- Arrow functions with defaults, keyword arguments, lexical closures, and
  recursive-program support.
- Raise, assert, try/except/finally, and sync or async with-expressions.

## Evaluation and runtime

- Async-first custom AST interpreter plus the `evaluate_sync` convenience
  boundary.
- Immutable Modules, Presets, standard hierarchy, Frame factories, child Frames,
  and controlled host-value overlays.
- Lazy result and failure snapshots, parent lookup, explicit missing-name
  fallbacks, per-name single-flight, circular diagnostics, and cancellation
  isolation.
- Atomic targeted recalculation, task-local evaluation limits, async
  context-manager finalization, deterministic close, and owned-resource cleanup.
- Definition context through `lhs()`, strict date conversion, and eager
  fixed-point recursion.

## Configuration

- UTF-8 `.lclcfg` documents with version declarations, definitions, comments,
  multiline expressions, and source origins.
- Asynchronous in-memory and file loading, source-ordered `using` expansion,
  deterministic precedence, caching, concurrency sharing, and cycle detection.
- Direct conversion from loaded configuration to runtime Module and Frame
  values.

## Dependencies and inspection

- Scope-aware static dependency extraction with eager, conditional, and deferred
  references.
- Immutable Module and Frame graphs, filtered queries, deterministic
  topological ordering, value terminals, and qualified lookup paths.
- Bounded dynamic lookup tracing, static/dynamic reconciliation, and immutable
  dependency snapshots.
- Non-evaluating definition lookup and variable trees with cache state, owners,
  typed values, failures, native values, canonical AST/function rendering, and
  evaluation stacks.

## Standard utilities

- Manifest-driven read-only namespaces and immutable standard presets.
- Reviewed iterable, text, immutable-data, strict JSON, date, and recursion
  helpers without ambient I/O or dynamic-code capabilities.
- Async three-state business-day calendars with canonical composition, bounded
  mappings, strict JSON loading, and dependency-aware cache retirement.
- Nested workflow task and step status trees with deterministic aggregation,
  locking, scoped mutation, context-manager finalization, and failure capture.

## Command-line framework

- Immutable invocation values, typed async commands, decorators, nested command
  groups, full-argument parsing, structured help, and platform-neutral process
  entry points.
- Preset/default/config/override Frame layering, boolean overrides, dry-run
  pass-through, isolated logging, opt-in task-local verbose tracing, and
  deterministic result/cleanup mapping.
- Built-in `builtins`, `parse_lcl`, and `eval_lcl` commands for inventory,
  inspection, and evaluation.

## Distribution quality

- Strict type checking, linting, 100% branch coverage, parser differential and
  property tests, concurrency and dependency stress tests, leak checks, and
  executable documentation.
- Reproducible source distribution and platform-independent wheel checks,
  clean-environment installation, metadata validation, and import smoke tests.
