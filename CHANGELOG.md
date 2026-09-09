# Changelog

## Unreleased

- Move repository hosting and project links to `gokurakujoudo/lclang` on
  GitHub, with GitHub Actions verification, tag builds and manual publishing.
- Export logger, runtime, resolved configuration and metric types from
  `lclang.logger`; share public `resolve_logger_config(frame)` between CLI and
  standalone `.lclcfg` applications, with handler defaults for an absent namespace.
- Preserve Gunicorn's graceful SIGTERM handler in the documented Uvicorn worker
  so replayed shutdown signals allow queued logs to drain and files to close.

## 1.0.8 - 2026-09-08

- Add `lclang.logger` process scopes, deferred writer-thread formatting, named
  sinks, immutable metrics, reversible stdlib takeover and warnings capture.
- Add permanent successor-linked file segments with independent UTC time and
  size rotation, failure isolation and cancellation-resilient draining.
- Unify CLI/Workflow logging through `logger.console`, `logger.file.<sink>` and
  `logger.file.default`, with LCL/CLI field precedence and explicit enabled
  overrides. Diagnostics use stderr; verbose affects enabled sinks only.
- Replace standalone logger handles with scoped ownership; update executable
  tutorials, source integration tests and server integration examples.
- Replace artifact installation smoke with a source CLI integration test;
  correct the logging override to `logger.log_dir` and retain resource cleanup.
- Remove archive audits, rebuild comparisons and installation validation.
  Restrict sdist to downstream code, typing data, build metadata, license and
  root README; tag pipelines build after verification for manual publishing.
- Run whitespace, Ruff, production policies, architecture checks and mypy
  before documentation and full behavioral coverage, including default stress.
- Count at most 200 production code-bearing physical lines per file. Tighten
  semantic naming, scoped rST exception checks and constant explanations, while
  removing redundant tutorial structure and test-file requirements.
- Share parser source spans and lexer lookahead, and centralize command
  validation and immutable snapshots at construction.
- Reuse operation-local Frame binding selections, remove thin API mixins and
  redundant state protocols, and organize evaluation, lifecycle and inspection
  implementations by responsibility without changing public import layers.
- Consolidate paired calendar algorithms and common operand validation while
  preserving IDs, singletons, three-state behavior and mapping caches.
- Export `lclang.utils.safe_repr` for protected single-line representations,
  masking, canonical rendering and exact truncation budgets; share it across
  diagnostics, workflow mappings and inspection.
- Isolate all ordinary failures in the optional lunch easter egg; retain
  cancellation and process-control propagation.
- Execute exact Markdown examples through shared fixtures, derive tutorial
  structure from one table of contents, centralize the CLI reference and correct
  date conversion, dynamic using and trusted capability descriptions.
- Require permission requests for blocked filesystem or temporary-directory
  operations rather than changing paths, isolation or checks to bypass them.

## 1.0.7 - 2026-09-02

- Add Frame proxy string indexing, sorted immediate child discovery,
  direct-child fallback, and dataclass materialization for independently
  overrideable scoped collections.
- Expose live environment variables through Python and canonical LCL `env`,
  while allowing scoped config, preset, mixin, and CLI overrides without
  mutating the process environment.
- Support position-sensitive f-string `using` targets evaluated from prior
  expanded definitions, explicit loader or CLI overrides, and canonical
  builtins in disposable Frames.
- Export standalone logging configuration and logger lifecycle utilities while
  retaining the CLI compatibility surface and scoped logger behavior.
- Add exact valueless `-o FORCE` to built-in parse/eval commands for strict
  marked RESULT syntax with source-aligned, masking-aware status-2 diagnostics.
- Extend the scoped-values tutorial with an executable nested-proxy dataclass
  list built from independently overrideable endpoint fields.
- Expand the configuration tutorial with executable value- and environment-
  selected f-string `using` targets, and add a downstream Python utilities
  tutorial covering environment, logging, standard helpers, and calendars.

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
