# Production and test module layout

## Production packages

The project grows through narrow packages rather than large cross-cutting
modules:

```text
src/lclang/
  ast/             immutable node values and visitor contracts
  lang/
    lexer/         tokens, string scanning and f-string scanning
    parser/        Pratt core, displays, comprehensions and special forms
    printer/       precedence-aware canonical source rendering
    evaluator/     node-family evaluation handlers and auto-await helpers
  runtime/         modules, presets and public runtime exports
    frame/         Frame core, mixins, cache lifecycle and inspection trees
    dependency/    static/dynamic analytics and qualified Frame graphs
  stdlib/          reviewed manifests, namespaces and async helpers
  config/          logical lines, includes, origins and config diagnostics
  cli/             typed contexts, parsing, routing, runners and built-ins
  workflow/        execution-status values, task/step handles and finalization
```

Shared public value objects and errors remain small top-level modules. Package
`__init__.py` files only re-export names; they contain no behavioural logic.
Every implementation file must stay below 200 physical lines. When a module
approaches the limit, split by a behavioural axis before adding more branches.

Dependencies flow inward: CLI may depend on config/runtime; config may depend
on language/runtime; runtime may depend on AST/language primitives. AST, source,
types, errors, and workflow status never import runtime, config, or CLI.

## Test packages

Tests mirror subsystem ownership:

```text
tests/
  ast/             node, visitor and round-trip contracts
  lang/            lexer/parser/printer/evaluator behaviour
  runtime/         module and preset behaviour
    frame/         cache, concurrency, lifecycle and inspection behaviour
    dependency/    static/dynamic and qualified graph behaviour
  stdlib/          manifest and async-helper behaviour
  config/          text, include, origin and diagnostic behaviour
  cli/             argv, routing, stream and exit-code behaviour
  workflow/        status values, aggregation, locking and scoped finalization
  support/         reusable factories, fake resources and corpus loaders
  stress/          opt-in scale, concurrency and leak scenarios
```

Within each subsystem, test paths mirror production paths one-for-one. For
example, `src/lclang/ast/base.py` is covered by `tests/ast/test_base.py`, while
`src/lclang/lang/lexer/scanner.py` is covered by
`tests/lang/lexer/test_scanner.py`. A test may span several production modules
only when it verifies an explicitly documented integration boundary; those
tests live in a sibling `test_integration_*.py` module.

A behaviour has one obvious owning test module. Tests assert public behaviour,
structured state, or diagnostics rather than private method calls. Shared
fixtures enter `tests/support` only after at least two subsystems need them.
Generated corpora and benchmarks remain separate from unit tests so the normal
quality loop stays fast and deterministic.
