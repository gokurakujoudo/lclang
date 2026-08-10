# M001: product and architecture specification

## Product

`pylcl` is a zero-runtime-dependency Python 3.14 library for application
authors who want expressive, lazily evaluated configuration. Inputs are trusted
configuration, not hostile programs. Releases are staged as 0.1 language and
runtime, 0.2 configuration files, 0.3 CLI framework, and 0.4 hardening.

## Language

LCL V1 owns its grammar. A pure-Python lexer and Pratt/recursive-descent parser
produce immutable custom AST nodes. The supported Python-like subset is listed
in milestone specifications before implementation. LCL adds null-safe access,
null coalescing, expression forms for functions/errors/context managers, and
PEP 798-style comprehension unpacking. It excludes assignment expressions,
lambda, yield, explicit await, imports, statements, and template strings.

## Runtime

The custom async interpreter is the only execution backend. Each evaluated node
resolves awaitables. A Frame caches values and failures, resolves parent values
in their defining Frame, supports task-level single-flight in one event loop,
and never invalidates cached dependants. Explicit recalculation atomically
replaces only the requested value.

## Public layers

1. `pylcl.lang`: tokens, AST, parser, printer, errors, and evaluator.
2. `pylcl.runtime`: modules, frames, limits, dependency graph, and presets.
3. `pylcl.config`: `.lclcfg` parser, source loading, includes, and diagnostics.
4. `pylcl.cli`: typed entrances, routing, argument parsing, and built-in tools.

## Quality and documentation

All product work follows the workflow in `AGENTS.md`. Public APIs are fully
typed and documented. Runtime source files stay below 200 lines. Each release
gate requires strict mypy, clean Ruff, 100% branch coverage, portable
build/install checks, and synchronized English and Chinese README status.

## Acceptance

- The specification contains the agreed product, language, runtime, package,
  security, release, and quality boundaries.
- README files describe only current implementation status.
- `progress.md` records M001 and links this specification.
