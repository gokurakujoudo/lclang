# M050: bilingual 0.1 tutorials, API guide, and executable examples

## Goal

Document the implemented 0.1 language/runtime workflow in English and Chinese
with examples that execute against the current package rather than drifting as
unchecked prose.

## Deliverables

- `docs/tutorials/runtime-quickstart.md` and
  `doc_cn/runtime-quickstart_cn.md` provide equivalent step-by-step workflows.
- `docs/reference/runtime-api.md` and `doc_cn/runtime-api_cn.md` document the
  root/runtime/stdlib API layers, lifecycle, concurrency, caching, recalculation,
  dependency snapshots, presets, limits, errors, and security boundary.
- Both documentation indexes link the implemented tutorial and API guide.
- Root README files gain installation/development status, one executable runtime
  quickstart, links to the full guides, and an explicit unreleased-version note.

## Contract

- English and Chinese quickstarts contain equivalent standalone `python` fenced
  examples using only root `pylcl` API. Each example must print exactly
  `{"message":"hello pylcl"}` followed by a dependency target line `json`.
- Tests extract those blocks from both quickstarts and both root README files,
  execute each with the active interpreter, and require zero exit status plus
  the exact output. Examples therefore include deterministic Frame cleanup.
- API guides distinguish root daily-workflow names from advanced
  `pylcl.runtime` and `pylcl.stdlib` surfaces. They explain snapshot caching,
  explicit no-dependant-invalidation recalculation, owner-aware dependencies,
  limits, close/cancellation, and standard preset scope.
- Documentation states that expressions are trusted configuration and not a
  hostile-input sandbox. It does not advertise config-file or CLI features that
  begin in later releases.
- Until M051 passes artifacts and clean-install gates, README wording says the
  0.1 implementation is complete but unreleased and metadata remains `0.0.0`.
- Link/heading/example acceptance lives in
  `tests/test_runtime_documentation.py`; no production code changes are needed.

## TDD evidence

RED requires structural tests to fail because the four guide files and README
quickstarts are absent. GREEN requires bilingual links/headings and all four
standalone examples to execute with exact output. DONE requires the complete
quality gate and synchronized README/progress documents.
