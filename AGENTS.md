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

## Tutorial maintenance

- `docs/tutorials/README.md` is the human-oriented introduction and the single
  ordered table of contents for the series. Keep it useful on its own, keep
  every published chapter linked, and never list planned chapters as available.
- Store topic chapters as `docs/tutorials/NN-topic-name.md` and their executable
  contracts as `tests/tutorials/test_NN_topic_name.py`. Keep the introduction's
  contracts in `tests/tutorials/test_introduction.py` and series-wide structure
  checks in `tests/tutorials/test_series.py`.
- Mark each complete, copyable Python example with
  `<!-- lclang-tutorial-exec -->`. A chapter test must execute the exact marked
  source from the Markdown rather than maintain a second approximation of it.
- Teach in a simple to composite progression. Start with the smallest useful
  operation, add one concept at a time, and finish with a realistic combination
  that demonstrates why the feature matters.
- Put observable results in inline `assert` statements when practical. Do not
  repeat those assertions in an `Expected result` section. Follow each example
  with enough prose to trace how names resolve, which branch or dependency runs,
  who owns state, and why the asserted value follows from the code.
- Examples must be deterministic and independent. Mock external connectivity;
  put file examples inside a separate `TemporaryDirectory`; close Frames and
  other owned asynchronous resources explicitly or with context managers.
- When adding, renaming, reordering, or retiring a tutorial, update the series
  table of contents, `docs/README.md`, matching tests, packaging inventory, and
  changelog together. Check previous/next navigation and remove stale files and
  references in the same change.
- Run the matching tutorial test first, then
  `python -m pytest tests/tutorials -q --no-cov`, and finally
  `python -m scripts.quality` before handing off the change.

## Sources of truth

- `docs/reference/`: language and public API contracts.
- `docs/tutorials/`: executable user workflows and examples.
- `tests/`: behavioral and distribution contracts.
- `progress.md`: concise inventory of the stable 1.0 feature set.
- `README.md`: user-visible implemented capability only.
- `pyproject.toml`: supported Python and tool configuration.

Do not advertise planned behavior as implemented. Preserve unrelated user
changes. Update this file only when durable architecture or workflow changes.
