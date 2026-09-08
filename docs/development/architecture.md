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
    frame/         Frame API, binding lookup, evaluation, cache lifecycle and inspection
    dependency/    static/dynamic analytics and qualified Frame graphs
  stdlib/          reviewed manifests, namespaces and async helpers
  config/          logical lines, includes, origins and config diagnostics
  logger/          process scope, queue writer, named sinks and permanent rotation
  cli/             typed contexts, parsing, routing, runners and built-ins
  workflow/        immutable task trees, execution, mappings, CLI and status
  utils/
    calendar/      async calendars, mappings, loaders, and manager utilities
```

Shared public value objects and errors remain small top-level modules. Package
`__init__.py` files only re-export names; they contain no behavioural logic.
Each production Python file has at most 200 code-bearing physical lines,
excluding imports, docstrings, pure comments, and blank lines. Multiline
expressions, signatures, and runtime strings count; compressing statements or
embedding executable source is not an alternative to concise algorithms and
responsibility-based modules. Scripts and tests are outside this size policy.

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
  logger/          configuration, ownership, output, timers and failure isolation
  cli/             argv, routing, stream and exit-code behaviour
  workflow/        definitions, execution, mappings, rendering and status
  utils/
    calendar/      calendar strategies, algebra, mapping, loading, and LCL integration
  support/         reusable factories, fake resources and corpus loaders
  stress/          default full-suite scale, concurrency and leak scenarios
```

Within each subsystem, tests correspond to production submodule responsibilities.
One test file may cover several closely related implementation files. Explicit
integration contracts live in `test_integration_*.py` modules. First pass the
existing tests, refactor production code, pass the same tests, and only then
reorganize test files and shared fixtures to match the resulting responsibilities.

A behaviour has one obvious owning test module. Tests assert public behaviour,
structured state, or diagnostics rather than private method calls. Shared
fixtures enter `tests/support` only after at least two subsystems need them.
Benchmarks remain separate from the quality gate. Deterministic stress and
property tests run in the default full behavior suite.

## Frame responsibilities

`runtime/frame/frame.py` owns Frame state and its public methods.
`binding_lookup.py` selects owner, kind and diagnostic path for one operation;
`host_bindings.py` validates and atomically publishes mixins. `evaluation.py`
reads selected values, while `evaluation_flights.py` coordinates cycles,
single-flight and recalculation. `cache_lifecycle.py` commits snapshots and
closes owned resources. `dependency_snapshots.py` owns static and dynamic
observations. `inspection_values.py`, `inspection_builder.py` and
`inspection_rendering.py` separate the public result, construction and display.
`frame_factory.py` and `evaluation_limits.py` contain reusable creation policy
and work budgets. Public package exports retain the supported import surface.

Calendar period boundaries, range boundaries, directional adjustments and sparse
filters share implementations by responsibility. Operand normalization preserves
encounter order for fallback and sorts only commutative compositions.
