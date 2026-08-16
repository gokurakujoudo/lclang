# Changelog

## Unreleased

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
