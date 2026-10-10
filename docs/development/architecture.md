# Production and test module layout

## Production packages

The project grows through narrow packages rather than large cross-cutting
modules:

```text
src/lclang/
  __version__.py   sole package version definition
  common/          cross-package source types, identifiers, defaults, masks and proxies
  error/           exceptions, diagnostic records, causes, groups and rendering
    codes/         e0-e9 enum vocabularies and parent-relative classifications
  lang/            preferred parsing and Module/Frame construction APIs
    common/        language records, grammar version, names and declaration markers
    ast/           immutable node families and visitor contracts
    engine/
      lexer/       tokens, string scanning and f-string scanning
      parser/      Pratt core, displays, comprehensions and special forms
      printer/     precedence-aware canonical source rendering
      evaluator/   node-family evaluation handlers
    runtime/       Modules, Presets and construction factories
      frame/       lookup, evaluation, cache lifecycle and inspection
      dependency/  static/dynamic analytics and qualified Frame graphs
    stdlib/        manifests, namespaces, calendar adapter and async helpers
  config/          logical lines, includes, origins and loading
  logger/          configuration, process scope, queue writer, sinks and rotation
  cli/             typed contexts, parsing, routing, runners and built-ins
  workflow/        task trees, execution, CLI and status
    mappings/      structure, annotations, binding and mapping diagnostics
  utils/
    calendar/      calendars, mappings, loaders and managers
```

Cross-package primitives live in `common/`; language-specific shared values live
in `lang/common/`. Errors live in `error/`; its root depends on code tables and
masking state. Source-aware records defer source-type imports until validation,
and rendering imports source adapters when called. This keeps primitive/error
imports acyclic. Package `__init__.py` files curate exports with static imports.
The root exports no API. Only `__init__.py` and the sole version definition,
`__version__.py`, remain directly under `src/lclang`.
Each production Python file has at most 200 code-bearing physical lines,
excluding imports, docstrings, pure comments, and blank lines. Multiline
expressions, signatures, and runtime strings count; compressing statements or
embedding executable source is not an alternative to concise algorithms and
responsibility-based modules. Scripts and tests are outside this size policy.

Dependencies flow inward: CLI may depend on config/runtime; config may depend
on language/runtime; runtime may depend on AST/language primitives. AST, source,
types, errors, and workflow status never import runtime, config, or CLI.
Logger Frame configuration depends on runtime and never imports CLI; CLI adds
parameter recognition and entry-point defaults around the shared resolver.

## Test packages

Tests mirror subsystem ownership:

```text
tests/
  error/           code registry, constructor, protocol, cause and cleanup contracts
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

`lang/runtime/frame/default_frame_scope.py` owns isolated fallback Frames. Direct workflows use
a task-local lookup scope; CLI invocation owners attach a fallback to their own
hierarchy. Neither mechanism rewrites borrowed parents or invalidates cached
dependencies. Factory definitions reuse the interpreter's single-flight and
failure caches. `workflow/variable_default.py` collects declarations; mapping-local
constructor fallbacks and scope-aware dependency discovery stay in `mappings/`.

`lang/runtime/frame/frame.py` owns Frame state and its public methods.
`binding_lookup.py` selects owner, kind and diagnostic path for one operation;
`host_binding.py` validates and atomically publishes mixins. `binding_evaluation.py`
reads selected values, while `evaluation_flight.py` coordinates cycles,
single-flight and recalculation. `cache_lifecycle.py` commits snapshots and
closes owned resources. `dependency_snapshot.py` owns static and dynamic
observations. `variable_inspection.py`, `inspection_builder.py` and
`inspection_rendering.py` separate the public result, construction and display.
`frame_factory.py` and `evaluation_limit.py` contain reusable creation policy
and work budgets. Public package exports retain the supported import surface.

Calendar period boundaries, range boundaries, directional adjustments and sparse
filters share implementations by responsibility. Operand normalization preserves
encounter order for fallback and sorts only commutative compositions.

## Workflow mapping responsibilities

`workflow/mappings/` owns recursive dataclass structure, specialized record
annotations, reference materialization, staged publication, and mapping logs.
Its `__init__.py` retains the mapping entry points used by workflow execution,
CLI analysis and static rendering. Tests for recursive and whole-record behavior
live in `tests/workflow/mappings/`.
