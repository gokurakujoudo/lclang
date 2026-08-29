# Changelog

## Unreleased

## 1.0.6 - 2026-08-29

- Scope CLI logger configuration beneath `logger`, print application `INFO`
  records to stdout, and include application `DEBUG` records there in verbose
  mode without changing the configured file threshold.
- Route application error logs to stderr even without file logging, and inject
  `__ymd__`, `__execution_timestamp__`, and `__command__` strings for use by
  logger configuration expressions.
- Use the configured structured log format for both file and terminal
  application records, require its level field, and make the bound log path the
  first file record.
- Refine the CLI audit into four readable records with a centered execution
  banner, exact redacted JSON argv, and sorted lazy winning configuration; stop
  appending logging argument tuples to the default format.
- Add workflow task/context lifecycle and typed verbose mapping records,
  dot-connected task Frame branches, traceback-bearing errors, one-record final
  trees, and optional `lunch.options` outcomes.
- Recommend grouped commented `.lclcfg` definitions with inferred scoped
  prefixes while retaining explicit `FRAME_PROXY` syntax for compatibility.
- Centralize CLI runtime variable keys and expose typed `__as_of_date__`,
  `__dryrun__`, and `__verbose__` bindings alongside the existing audit values;
  remove duplicate `as_of_date` and `dryrun` bindings and rename `cli_params`
  to `__cli_params__`.

## 1.0.5 - 2026-08-28

- Sort CLI configuration parameters by name in generated help without changing
  their declaration or runtime binding order.
- Add a formal default CLI log format and a masked four-line execution preamble
  covering the selected command, log path, normalized command line, and
  CLI-owned execution configuration.
- Add validated tree workflows with typed variable mappings, scoped resource
  contexts, deterministic execution and cleanup, covered failures, static tree
  rendering, inferred CLI commands, recursive command discovery, and an
  executable energy-settlement case-study tutorial.
- Add non-empty `{name=expression}` record displays that evaluate fields
  left-to-right into shallowly immutable, attribute-accessible `LclRecord`
  values shared by LCL and Python.
- Add trailing-`!` exact-name masking across configuration, Modules, Presets,
  Frames, resolver mappings, and CLI bindings. Masking survives same-name
  overrides and renders lclang-owned verbose and inspection payloads as
  `*masked*` without changing runtime values.

## 1.0.4 - 2026-08-25

- Add qualified scoped values backed by lazy Frame proxies across Python,
  configuration files, CLI overrides, inspection, and dependency analysis.
- Add uncached `Frame.evaluate()` expressions with `lhs()` set to `"<expr>"`.

## 1.0.3 - 2026-08-23

- Added `--verbose` tracing after CLI leaf commands for top-level expression
  parsing, typed value provenance, caching, fallbacks, and evaluation. Traces
  stream to stderr and enabled invocation log files without changing the
  existing `-v/--version` behavior.
- Rebuilt the tutorial collection around one human-oriented introduction and
  twelve focused chapters. Examples progress from simple to composite
  operations, assert their results inline, explain how those results are
  derived, and execute from one matching unit-test module per document under
  `tests/tutorials`.
- Documented the tutorial maintenance contract for future contributors and
  rebuilt the root README as a standalone PyPI landing page that presents the
  full language, runtime, configuration, tooling, and utility offering without
  relying on repository or external links.

## 1.0.2 - 2026-08-19

- Added the async three-state business-day calendar subsystem, including
  canonical algebra, builtin patterns, factories, immutable date mappings,
  strict JSON loading, concurrent named-calendar management, and retirement.
- Exposed calendar construction and manager helpers through canonical LCL
  builtins while moving standard namespaces into `LCL_BUILTINS`.
- Added complete calendar reference and tutorial documentation plus independent
  behavioral, documentation, and release-candidate quality gates.
- Frames now support `async with`, the preferred lifecycle syntax for
  deterministic owned-resource cleanup.
- `Frame.get()` now accepts an explicit missing-name fallback, with the public
  `NO_FALLBACK` sentinel preserving the existing exception behavior by default.

## 1.0.0 - 2026-08-10

- Stable LCL expression language with arrow functions, canonical source
  rendering, structured diagnostics, and a custom async interpreter.
- Lazy hierarchical runtime Frames with caching, concurrency control, limits,
  recalculation, dependency analysis, inspection, and deterministic cleanup.
- Composable UTF-8 `.lclcfg` loading with asynchronous includes, precedence,
  origins, caching, and cycle detection.
- Typed command-line application framework, reviewed standard utilities, and
  nested workflow status tools.
- Python 3.14 support, zero third-party runtime dependencies, strict typing,
  complete branch coverage, and portable wheel/source distributions.
