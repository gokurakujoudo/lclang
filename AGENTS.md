# lclang Agent Handoff

Read this file, `progress.md`, the root `README.md`, and the relevant user or
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
- Production class and function names must describe their purpose without an
  underscore prefix. Only Python protocol methods may use required dunder
  spellings. Avoid generic `internal` prefixes; curate exports with `__all__`.
- A `Frame` is safe for concurrent tasks in one event loop, not across loops.
- Cached values are snapshots. Recalculation never invalidates dependants.
- Each production Python file contains at most 200 code-bearing physical lines,
  excluding imports, docstrings, pure comments, and blank lines. Multiline
  signatures, expressions, and runtime strings count by their physical lines.
  Do not compress statements or move code into strings to evade the limit.
  Split modules by responsibility, using filenames that explain their contents.
- Every production docstring is English rST. Functions and methods document how
  they work, every parameter with `:param name:`, results with `:returns:` unless
  no value is returned, and intentional exceptions with `:raises Type:`.
  Useful special behavior may use an rST `.. note::`; do not add notes that
  merely restate ordinary lifecycle or ownership. Value classes document
  constructor fields and edge cases with the same conventions.
- Document every named constant and constant group, including enums, with its
  units (or their absence), source, purpose, and choice rationale. A coherent
  group may share its explanation. Do not invent external sources or annotate
  every ordinary control-flow literal. These production policies apply only to
  `src/lclang`; scripts and tests still follow Ruff and strict mypy.
- Unit tests mock external connectivity and isolate file input/output in a
  separate `TemporaryDirectory`.
- CLI test configuration sources are static fixtures declared with their cases.
  Enabled logs are rooted in per-test temporary directories.

Runtime packages and tests follow `docs/development/architecture.md`. Tests
mirror production subsystem boundaries; reusable fixtures live in dedicated
support modules.

## Required workflow

For bug fixes:

1. Update the relevant English reference or guide.
2. Add a behavioral test and prove it fails. Cover practical sunny, rainy, and
   composite cases where applicable.
3. Implement the smallest correct behavior and prove it passes.
4. Refactor, then run focused and complete quality checks.
5. Update the root README, changelog, or feature inventory when their
   public claims change.

New features may iterate through prototypes before their final contract is
settled, but acceptance still requires reference documentation and behavioral
tests. For refactors, first pass the existing tests, change production code,
pass those tests again, then reorganize test ownership and verify again.
Tests correspond to subsystem and submodule responsibilities, not necessarily
one production file each. Documentation-only work uses link, structural, or
executable-example checks appropriate to the changed artifact.

If tests or tools are blocked by filesystem or temporary-directory permissions,
stop the affected operation and ask the user for the required permission. Do not
relocate temporary files, change temporary-directory environment variables,
weaken isolation, skip checks, or use another path solely to work around the
permission failure without the user's authorization. Continue independent work
that does not require that permission.

## GitHub feature development

Use this lifecycle for feature development and bug fixes:
`issue -> feature branch -> pull request -> squash merge -> branch cleanup`.

1. Create or reuse an issue in `gokurakujoudo/lclang` before implementation.
   Record the problem, scope, public behavior, and acceptance criteria; avoid
   duplicate issues for the same work.
2. Fetch `origin`, preserve unrelated local changes, and create a feature branch
   from current `origin/main`. Use `codex/<issue-number>-<short-description>`.
   Keep implementation, tests, and documentation together on that branch;
   do not develop directly on `main` or `release`.
3. Follow the required workflow above, update the relevant documentation and
   `CHANGELOG.md` under `Unreleased`, and run `python -m scripts.quality` before
   the final code handoff. Include stress tests and retain 100% branch coverage.
4. Commit and push the branch, then open a PR targeting `main` with
   `Closes #<issue-number>`. Describe the final behavior, relevant limitations,
   and actual validation results; update the description when scope changes.
5. Wait for all applicable CI checks on the latest PR head, including push and
   pull-request verification and builds. Fix failures and check the new head
   again. Results from an earlier commit do not approve a later commit; jobs
   intentionally excluded by workflow conditions are not missing checks.
6. Unless the user requests a draft or review-only handoff, squash merge once
   checks pass and merge requirements are satisfied. Guard the merge with the
   expected head SHA so a concurrent update cannot merge unverified work.
   Confirm the PR is merged and its linked issue is closed.
7. Synchronize local `main`. After confirming that the implementation branch
   contains no work added after the merged PR head, delete its remote and local
   copies. Squash merging does not preserve feature-commit ancestry, so verify
   the merged content before forcing local branch deletion if necessary.
   Finish on `main` and report any unrelated work left in the checkout.

Feature completion does not itself publish a version. When the user also
requests a release, complete the release workflow before final branch cleanup.

## Version release

Use this lifecycle when a version release is requested:
`version update -> tested PR -> squash merge to main -> fast-forward release
-> CI verification/build -> PyPI -> version tag and GitHub Release`.

1. Prepare the requested unused stable `1.0.x` version on the feature branch,
   or on a dedicated branch using the issue/PR workflow above. Update both
   `pyproject.toml` and `src/lclang/_version.py` to the same version. Move the
   changes being released into a nonempty `CHANGELOG.md` section named
   `## <version> - YYYY-MM-DD`, retaining `Unreleased` for future changes.
2. Validate release-note extraction with `scripts.release_notes`, run the full
   quality gate after the version update, and wait for the updated PR's CI.
   Squash merge only the verified head; version preparation must reach `main`
   before publication. Never add release-only commits on `release`.
3. Fetch the merged commit and verify that its content matches the tested PR.
   Fast-forward the persistent `release` branch to that exact commit on `main`
   and push it to `origin`. Do not force-update `release`, publish a feature
   branch, or include unreviewed work in the publishing commit.
4. Use the existing [.github/workflows/ci.yml](.github/workflows/ci.yml)
   pipeline. A push to `release` verifies ancestry and version notes, runs the
   full quality gate and builds, publishes the built wheel and source archive
   to PyPI with Trusted Publishing, then creates the matching GitHub tag and
   Release with changelog notes and those same distribution artifacts.
5. Tags use the exact package version without a `v` prefix. The version tag,
   GitHub Release, and PyPI artifacts must identify the same publishing commit
   and version. Let CI create the tag and Release after PyPI succeeds; do not
   create a parallel manual release or move an existing version tag.
6. Wait for publishing to finish and verify the final outcomes, not merely
   workflow dispatch: successful publication, the expected tag target, a
   published GitHub Release, and both attached distribution files. Check the
   merged `main` workflow and applicable documentation deployment as well.
   If PyPI succeeds but GitHub Release creation fails, rerun only the failed
   job; do not repeat the successful upload. Published PyPI versions are
   immutable, so changed artifacts require a new version.
7. Fetch the published tag, retain the persistent `main` and `release` branches,
   remove the completed implementation branch locally and remotely, and return
   to `main`. Report the version, PR, Release/PyPI links, checks, and cleanup.

See the [development guide](docs/development/README.md) for CI configuration,
Trusted Publishing setup, and supported manual recovery procedures.

## Tutorial maintenance

- `docs/tutorials/README.md` is the human-oriented introduction and the single
  ordered table of contents for the series. Keep it useful on its own, keep
  every published chapter linked, and never list planned chapters as available.
- Store topic chapters as `docs/tutorials/NN-topic-name.md`. Parameterized tests
  execute chapter examples; special fixture contracts and series structure
  retain their own tests. Do not require one test file per chapter, minimum
  article lengths, fixed slogans, or arbitrary exact example counts.
- Mark each complete, copyable Python example with
  `<!-- lclang-doc-exec -->`. A documentation test must execute the exact marked
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
- When adding, renaming, reordering, or retiring a tutorial, update the single
  series table of contents, navigation, and changelog. Tests discover chapters
  from that table and compare it with published files; the documentation home
  links to the series introduction instead of duplicating its inventory.
- During editing, run affected checks. Example edits execute the exact changed
  examples; structural edits run all documentation tests with `--no-cov`.
  Each completed code-refactor stage and final code handoff run
  `python -m scripts.quality`, including all stress tests. Do not repeat the
  same tutorial suite through several mandatory nested commands.

## Sources of truth

- `docs/reference/`: language and public API contracts.
- `docs/tutorials/`: executable user workflows and examples.
- `tests/`: behavioral, source smoke, and executable documentation contracts.
- `progress.md`: concise inventory of the stable 1.0 feature set.
- `README.md`: user-visible implemented capability only.
- `pyproject.toml`: supported Python and tool configuration.

Do not advertise planned behavior as implemented. Preserve unrelated user
changes. Update this file only when durable architecture or workflow changes.
