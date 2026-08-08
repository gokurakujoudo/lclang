# M050: 0.1 tutorials, API guide, and executable examples

## Goal

Document the implemented 0.1 language/runtime workflow with examples that
execute against the current package rather than drifting as unchecked prose.
The post-milestone tutorial refactor uses one English beginner-to-advanced path;
existing Chinese API reference remains available while tutorial translation is
deferred.

## Deliverables

- `docs/tutorials/README.md`, `runtime.md`, `lcl_examples.md`, and
  `config_file.md` provide installation, runtime concepts, complete language
  examples, and file integration without one oversized cheatsheet.
- `docs/reference/runtime-api.md` and `doc_cn/runtime-api_cn.md` document the
  root/runtime/stdlib API layers, lifecycle, concurrency, caching, recalculation,
  dependency snapshots, presets, limits, errors, and security boundary.
- Documentation indexes link the implemented tutorial path and API guides.
- Root README files gain installation/development status, one executable runtime
  quickstart, links to the full guides, and an explicit unreleased-version note.

## Contract

- Marked Python tutorial examples execute independently with the active
  interpreter; every gallery LCL fence parses, and advanced fixed-point,
  Fibonacci, and quicksort examples execute with deterministic Frame cleanup
  where Frames are owned.
- API guides distinguish root daily-workflow names from advanced
  `pylcl.runtime` and `pylcl.stdlib` surfaces. They explain snapshot caching,
  explicit no-dependant-invalidation recalculation, owner-aware dependencies,
  limits, close/cancellation, and standard preset scope.
- Documentation states that expressions are trusted configuration and not a
  hostile-input sandbox. It does not advertise CLI features that begin in later
  releases.
- Until M051 passes artifacts and clean-install gates, README wording says the
  0.1 implementation is complete but unreleased and metadata remains `0.0.0`.
- Link/heading/example acceptance lives in `tests/test_tutorials.py`; no
  production code changes are needed.

## TDD evidence

RED requires structural tests to fail because the four tutorial files are
absent and superseded guides remain. GREEN requires valid links/headings,
complete language-gallery parsing, and all marked standalone examples to
execute. DONE requires the complete quality gate and synchronized
README/progress documents.
