# lclang Agent Handoff

Read this file, `progress.md`, both root README files, and the relevant user or
reference documentation before changing the project.

## Project identity

- Distribution and import name: `lclang`.
- Production package root: `src/lclang`.
- Runtime: Python 3.14 or newer; no third-party runtime dependencies.
- License: MIT.
- Release line: stable 1.0.
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
- Source files stay below 200 lines, excluding docstrings and imports. Split
  modules by responsibility.
- Every production docstring is English rST. Functions and methods document how
  they work, every parameter with `:param name:`, results with `:returns:` unless
  no value is returned, and intentional exceptions with `:raises Type:`.
  Useful special behavior may use an rST `.. note::`; do not add notes that
  merely restate ordinary lifecycle or ownership. Value classes document
  constructor fields and edge cases with the same conventions.
- Add a descriptive comment for every constant value.
- Unit tests mock external connectivity and isolate file input/output in a
  separate `TemporaryDirectory`.
- CLI test configuration sources are static fixtures declared with their cases.
  Enabled logs are rooted in per-test temporary directories.

Runtime packages and tests follow `docs/development/architecture.md`. Tests
mirror production subsystem boundaries; reusable fixtures live in dedicated
support modules.

## Required workflow

For behavior changes:

1. Update the relevant English reference or guide.
2. Add a behavioral test and prove it fails. Cover practical sunny, rainy, and
   composite cases where applicable.
3. Implement the smallest correct behavior and prove it passes.
4. Refactor, then run focused and complete quality checks.
5. Update both README files, the changelog, or the feature inventory when their
   public claims change.

For a bug, reproduce it with a failing test before fixing it. Documentation-only
work uses link, metadata, structural, or executable-example checks appropriate
to the changed artifact.

## Sources of truth

- `docs/reference/`: language and public API contracts.
- `docs/tutorials/`: executable user workflows and examples.
- `tests/`: behavioral and distribution contracts.
- `progress.md`: concise inventory of the stable 1.0 feature set.
- `README.md` and `README_cn.md`: user-visible implemented capability only.
- `pyproject.toml`: supported Python and tool configuration.

Do not advertise planned behavior as implemented. Preserve unrelated user
changes. Update this file only when durable architecture or workflow changes.
