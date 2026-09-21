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
- Tuple, list, set, dictionary, and immutable named-record displays; generator,
  list, set, and dictionary comprehensions; sync and async iteration.
- Arrow functions with defaults, keyword arguments, lexical closures, and
  recursive-program support.
- Raise, assert, try/except/finally, and sync or async with-expressions.

## Evaluation and runtime

- Async-first custom AST interpreter plus the `evaluate_sync` convenience
  boundary.
- Immutable Modules, Presets, standard hierarchy, Frame factories, child Frames,
  and controlled host-value overlays.
- Exact-name trailing-bang masking metadata across binding sources, hierarchy
  overrides, verbose diagnostics, and inspection rendering.
- Qualified scoped bindings with lazy Frame proxies across Modules, presets,
  configuration, CLI overrides, and parent lookup.
- Equivalent proxy attribute/index access, alphabetical child discovery,
  direct-child fallback, and dataclass materialization.
- Canonical live environment lookup with non-mutating scoped overrides.
- Unnamed `Frame.evaluate()` expressions with Frame lookup and `lhs()` ownership.
- Lazy result and failure snapshots, parent lookup, explicit missing-name
  fallbacks, per-name single-flight, circular diagnostics, and cancellation
  isolation.
- Atomic targeted recalculation, task-local evaluation limits, async
  context-manager finalization, deterministic close, and owned-resource cleanup.
- Definition context through `lhs()`, strict date conversion, and eager
  fixed-point recursion.

## Configuration

- UTF-8 `.lclcfg` documents with version declarations, definitions, comments,
  multiline expressions, source origins, and sticky masked-key declarations.
- Asynchronous in-memory and file loading, source-ordered `using` expansion,
  deterministic precedence, caching, concurrency sharing, and cycle detection.
- Position-sensitive f-string `using` targets evaluated from prior definitions,
  call or CLI overrides, and canonical builtins in disposable Frames.
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
- Caller-owned, thread-safe Snowflake ID generation through `lclang.utils` and
  the canonical LCL `SnowflakeGenerator` builtin, with explicit worker IDs and
  fail-fast clock rollback, sequence exhaustion, and timestamp bounds.
- Reviewed iterable, text, immutable-data, strict JSON, date, and recursion
  helpers without ambient I/O or dynamic-code capabilities.
- Process-scoped queue logging with named sinks, template defaults, UTC time/size
  rotation, permanent linked segments, diagnostics and reversible stdlib takeover;
  public logger/runtime/configuration/metric types and async Frame configuration
  resolution for standalone applications; a live Python environment utility.
- Async three-state business-day calendars with canonical composition, bounded
  mappings, strict JSON loading, and dependency-aware cache retirement.
- Validated tree workflows with typed dataclass mappings, named variables,
  task-local context resources, parent-first depth-first execution, explicit
  publication, reverse cleanup, static rendering, and complete status trees.
  Workflow `lcl_mixin` snapshots expose host values and callables to configs and tasks.
- Generic variable annotations and whole-record workflow mappings with shallow
  scope-to-record conversion and record-to-scope publication.
- Nested task and step status management with covered-failure semantics,
  deterministic aggregation, locking, scoped mutation, and failure capture.

## Command-line framework

- Entrance `lcl_mixin` snapshots share host defaults across routed commands,
  configuration expressions, and workflow tasks while preserving local precedence.

- Immutable invocation values, typed async commands, decorators, nested command
  groups, full-argument parsing, scope-grouped A-Z parameter help with static defaults, and
  platform-neutral process entry points.
- Preset/default/config/override Frame layering, boolean overrides, dry-run
  pass-through, scoped logger configuration with invocation date, timestamp,
  command, parameters, as-of date, dry-run, and verbose runtime values exposed
  only through reserved double-underscore keys and shared constants. Named
  logger configuration shares LCL/CLI override precedence; enabled flags inherit
  only when absent. One writer handles stderr and files, redacted argv and lazy
  audits, runtime verbose tracing, and complete output drain.
- Built-in `builtins`, `parse_lcl`, and `eval_lcl` commands for inventory,
  inspection, evaluation, and optional strict marked-RESULT parsing.
- Workflow commands with inferred external parameters, help and masks,
  dot-branch lifecycle and verbose typed mapping logs, one-record final status
  trees and recursive package discovery.

## Source quality

- Strict type checking, linting, 100% branch coverage, parser differential and
  property tests, concurrency and dependency stress tests, leak checks, and
  executable documentation.
- Source CLI smoke, default full stress execution, and minimal downstream sdist
  contents. CI builds follow source verification on every run; the `release`
  branch publishes to PyPI with Trusted Publishing, and tags support manual publishing.
- Public `lclang.utils.safe_repr` protects single-line value rendering, masking,
  canonical renderers and exact truncation budgets.
