# Changelog

## Unreleased

No unreleased changes.

## 0.2.0 release candidate — 2026-08-08

- `Frame` now accepts a string or omitted ID, defaulting direct construction to
  `frame-<module name>`, and the complete subsystem now lives under
  `pylcl.runtime.frame`.
- Added side-effect-free `Frame.inspect_variable()` trees with cache/host state,
  selected definitions, exact lookup paths, owners, dependency branches,
  finite cycle rendering, compact reprs, and markdown-style lines.
- Inspection trees now collapse repeated direct dependency names in first-seen
  order while retaining the same variable independently on separate branches;
  graphs, traces, and snapshots remain occurrence-preserving.
- Refined inspection's source-oriented repr to
  `name@frame/path: [definition ](Status) typed-payload`: ASTs have clear status
  spacing, external values omit definition text, values render as `type: repr`,
  and errors render as `ErrorType: message`.
- Made `lhs()` lexical inside LCL function values, so call arguments retain the
  caller owner while function bodies retain their defining variable name.
- `evaluate_sync` now accepts expression source text directly, and
  `FrameFactory.create()` defaults its ID to `frame-<module name>`.
- Added a complete dependency analytics tutorial and reorganized internal
  analytics into `runtime/dependency/`, including nested Frame graph modules;
  redundant evaluator/printer/config filenames now describe their contents.

- Added definition-scoped `lhs()` in `LCL_ROOT` and strict locale-independent
  `parse_ymd`/`to_ymd` calendar conversion in `LCL_BUILTINS`.
- Extended dependency graph construction to accept a Frame and report qualified
  definition/value bindings, exact lookup paths, and unresolved references
  without evaluating or touching runtime traces.
- Added reusable default-parent policy to `FrameFactory`; configuration-created
  Frames now use the canonical root/builtin hierarchy by default.

- Replaced the oversized user cheatsheet and legacy runtime quickstarts with an
  English tutorial path covering installation, Modules and Frames, the complete
  LCL feature gallery, fixed-point recursion, quicksort, and `.lclcfg`
  integration through executable examples.

- Added UTF-8 `.lclcfg` parsing with optional version metadata, colon
  definitions, comments, explicit backslash continuation, and eager
  source-file magic constants.
- Added async path-backed `using` expansion with deterministic later-wins
  precedence, complete shadow history, cycle detection, loading limits,
  single-flight caching, cancellation isolation, and filesystem containment.
- Added the curated `pylcl.config` parsing/loading API and runtime Module,
  FrameFactory, and guaranteed-cleanup evaluation bridge.

- Added the preferred `define_module` and `define_frame` construction shortcuts
  with the explicit `LCL_ROOT -> LCL_BUILTINS -> LCL_RUNTIME -> LCL_IMPORTS ->
  user module` lookup hierarchy.
- Added non-evaluating `Frame.has` and `Frame.get_definition` inspection backed
  by the same recursive owner-selection rule as `Frame.get`.
- Added `Frame.derive` as the preferred concise constructor for independent
  child Frames with detached local values.
- Added atomic right-biased `Frame.mixin` host-value updates while preserving
  cached definition snapshots until explicit recalculation.

## 0.1.0 release candidate — 2026-08-06

The first released `pylcl` language/runtime surface includes:

- a pure-Python, versioned expression grammar with immutable AST values,
  canonical printing, comprehensions, functions, closures, errors, and context
  management;
- an async-first evaluator with a synchronous convenience boundary, hierarchical
  Frame caching, dependency inspection, recalculation, limits, cancellation
  isolation, and deterministic cleanup;
- immutable modules, presets, reusable Frame factories, dependency graphs, and
  a reviewed standard preset with `iter`, `text`, `data`, and `json` namespaces;
- bilingual tutorials, API guidance, and executable examples;
- zero-dependency runtime packaging for Python 3.14+ with a platform-independent
  wheel and source distribution release gate.

`pylcl` is intended for trusted application configuration. It is not a hostile-
code sandbox; host-provided values and callables retain ordinary Python powers.
