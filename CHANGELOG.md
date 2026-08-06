# Changelog

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
