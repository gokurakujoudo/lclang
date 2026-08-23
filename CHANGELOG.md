# Changelog

## Unreleased

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

## 1.0.2 - 2026-08-16

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
