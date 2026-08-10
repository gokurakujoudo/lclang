# pylcl Agent Handoff

Read this file, `progress.md`, the active milestone specification, and both
README files before changing the project.

## Project identity

- Distribution and import name: `pylcl`.
- Runtime: Python 3.14 or newer; no third-party runtime dependencies.
- License: MIT.
- Target: complete and verify the 0.4 release described in `progress.md`.
- Security model: trusted configuration language, not a hostile-code sandbox.

## Non-negotiable architecture

- The parser is a pure-Python lexer plus Pratt/recursive-descent parser.
- Execution uses the custom AST interpreter only. Do not add ANTLR, Java,
  `eval`, `exec`, Python-AST compilation, or a bytecode backend.
- Public evaluation is async-first. `evaluate_sync` is the only synchronous
  convenience boundary.
- No class or function name can start with an underscore.
- A `Frame` is safe for concurrent tasks in one event loop, not across loops.
- Cached values are snapshots. Recalculation never invalidates dependants.
- Source files must stay below 200 lines, excluding docstrings and imports. Split modules by responsibility.
- Every production docstring is English rST. All functions and methods (including private ones)
  document how it works, and every parameter with `:param name:`, their result with `:returns:` unless no return or `None`,
  every intentional exception with `:raises Type:`, and genuinely useful special
  behaviour with an rST `.. note::`. Do not add notes that merely restate the
  declaration, owning subsystem, or ordinary lifecycle. All value classes
  (including private ones) document constructor fields
  and edge cases with the same conventions.
- A Comment for each constant values to describe it.
- In unittest, mock any external connectivities, and use separated TemporaryDirectory to hold file input and outputs.
- CLI unittest configuration sources are static fixtures declared with their test
  cases. Every enabled log file is rooted in a per-test temporary directory that
  is cleaned automatically.

Runtime packages and tests follow `docs/architecture/module-layout.md`. Tests
mirror production subsystem boundaries; reusable fixtures live in dedicated
support modules rather than unrelated test files.

## Required workflow

For every implementation milestone:

1. Write or update its English specification in `docs/specs/`.
2. Add a behavioural test and run it to prove RED, test must include practical and meaningful sunny, rainy, composite-complex cases.
3. Implement the smallest correct behaviour and prove GREEN.
4. Refactor, then run milestone and full quality checks.
5. Update `README.md`, `README_cn.md`, and `progress.md`.
6. Mark `DONE` only with commands and evidence recorded in `progress.md`.

For a bug, reproduce it with a failing test before fixing it. Documentation-only
milestones use link, metadata, or structural checks rather than artificial unit
test failures.

## Sources of truth

- `progress.md`: current work, status, evidence, and release gates.
- `docs/specs/`: behaviour and public contracts.
- `README.md` and `README_cn.md`: user-visible implemented capability only.
- `pyproject.toml`: supported Python and tool configuration.

Do not advertise planned behaviour as implemented. Preserve unrelated user
changes. Update this file only when durable architecture or workflow changes.
