# Changelog

## Unreleased

- Infer dataclass CLI field help and override paths without duplicating workflow
  variables or eagerly calling default factories. Add selective `flatten_to_dict`
  for reference-preserving dotted presets; retain Frame object/path exclusivity.

- Add explicit `ValueBox` and `CallableBox` values with shallow workflow binding
  conversion, preserving zero runtime dependencies and typed projections.
  Add dedicated variable-type and mapping-shape chapters with executable best
  practices, conversion costs and supported boundaries.
- Improve business event readability with aligned multiline fields and public
  synchronous `make_repr_lines` and `make_multi_log_lines` formatting tools.

## 1.0.13 - 2026-09-23

- Add typed `utils.invoke` for synchronous and asynchronous callbacks, and
  `TaskContext.log_event` for explicitly selected and masked business values.
  Preserve application caller attribution with standard and lclang loggers.
  Extend the Python utilities tutorial with an executable resource, projection,
  nested mapping, default configuration, and event logging example.

- Add variable `default` and lazy sync/async `default_factory` bindings with
  per-execution caches, common LCL and mapping lookup, dataclass field fallback,
  and optional CLI help that never invokes factories.

- Make context resources visible throughout their owning workflow subtree,
  matching CLI inference and inherited masking. Preserve business and cleanup
  failures together while cancellation continues to propagate.

- Resolve nested workflow dataclass mappings consistently across execution,
  atomic publication, CLI discovery, and masked diagnostics. Add typed read-only
  variable field projections with root-variable dependency ownership.

## 1.0.12 - 2026-09-21

- Add action-only `TaskContext.skip_children()` to omit child subtrees without
  status records, preserving output publication and cleanup even on later failures.

- Support generic workflow variable annotations and whole-record `.quote`
  argument/output mappings, including scope-to-record inputs and shallow
  record-to-scope output publication.

- Classify defaulted workflow CLI inputs as optional, display safe static defaults,
  and group parameter help alphabetically by scope with concise type annotations.
  Accept qualified CLI preset names while preserving reserved-name checks.

## 1.0.11 - 2026-09-19

- Add `CliEntrance(..., lcl_mixin={...})` to share host values and callables
  across every routed command's configuration and workflow tasks.

- Add workflow `lcl_mixin` host bindings for configuration expressions and tasks,
  with shallow definition snapshots and CLI host-default integration.

- Move the documentation logo from the sidebar to the top of the home page content.

- Use the available documentation width with centered content, and simplify code
  blocks to one bordered surface with compact Copy controls.

- Replace the custom Pages renderer with MkDocs and its Read the Docs theme,
  preserving page URLs, canonical tutorial navigation, local search, and the logo.
  Highlight code at build time with LCL/configuration support, exact code copying,
  and escaped plain-text fallback.

- Adopt the supplied geometric lclang logo across the README, documentation,
  Wiki export, and browser icons.

## 1.0.10 - 2026-09-10

- Add `lclang.utils.SnowflakeGenerator` and the matching canonical LCL builtin
  for thread-safe 63-bit IDs with explicit worker assignment, validated epochs,
  and fail-fast clock/sequence bounds. Document ownership, uniqueness conditions,
  and Python/LCL composition with executable utility tutorial examples.
- Replace the Pages introduction with a complete documentation site generated
  from existing Markdown, with grouped navigation, section search, page contents,
  dark mode, code copying, mobile and print layouts, and verified CI artifacts.
- Read the README version badge from PyPI JSON with a shorter badge cache so
  it reflects newly published versions sooner.

## 1.0.9 - 2026-09-09

- Publish pushes to the `release` branch to PyPI after verification and builds,
  using Trusted Publishing and the dedicated `pypi` environment. Require release
  commits to come from `main` and create matching version tags and GitHub Releases.
- Add a shared PNG logo to the website, README, Wiki, and browser icons.
- Publish tested documentation to GitHub Wiki with preserved examples and
  rewritten navigation; add a GitHub Pages introduction and gated deployment.
- Export JUnit test results and portable raw, XML, JSON and HTML coverage
  reports; retain available CI reports on failure and add README status badges.
- Build wheel and source distributions after verification on every GitHub CI
  run, and declare GitHub as the package homepage in PyPI metadata.
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
