# M092: CLI documentation and 0.3 release gate

## Goal

Document the verified CLI surface in both languages, synchronize version 0.3.0,
and validate installed command behaviour from wheel and sdist artifacts.

## Module and test layout

- English CLI tutorials/reference live under `docs/`; equivalent Chinese content
  lives under `doc_cn/`, linked from both indexes and root READMEs.
- Documentation checks live in `tests/cli/test_documentation.py`; build/install
  checks use the established release scripts and smoke tests.
- Any production edits preserve sub-200-line modules and complete English rST
  docstrings for every public/private callable and value class.

## Contract

- Bilingual docs cover application declarations, fixed-arity argv grammar,
  routing, help, config binding/precedence, execution, dry-run, built-ins, status
  codes, lifecycle, platform behaviour, and trusted-input scope.
- Every documented command has an independently executable example whose exact
  stdout, stderr, and status are tested. Root READMEs advertise no 0.4 hardening
  result as already complete.
- `pyproject.toml`, `pylcl.__version__`, changelog, API inventory, and console
  metadata become exactly 0.3.0 and agree.
- Build/inspect wheel and sdist, install each without dependencies in separate
  clean Python 3.14+ environments, and run import, help, version, config-check,
  dry-run, successful handler, usage failure, and runtime failure smoke cases.
- The release gate includes strict mypy, Ruff, source/docstring checks, all tests
  with branch threshold, bilingual link/example parity, artifact-content audit,
  and Windows/Linux CI evidence.

## TDD matrix

- Sunny: execute all bilingual examples and the clean-install success matrix for
  both artifacts.
- Rainy: fail on stale versions, broken links, translation/API drift, wrong
  stream/status, undeclared files/exports, repository leakage, or missing scripts.
- Composite-complex: clean-install, load a Unicode include graph, route a nested
  command, dry-run it, then execute an async LCL handler and verify cleanup.

## Completion evidence

Record exact build/inspect/install/smoke/full-quality commands, OS results,
coverage/counts, artifact names/hashes, and completion date in `progress.md`.
