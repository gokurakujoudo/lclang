# M072: configuration documentation and 0.2 release gate

## Goal

Document only the verified configuration surface, synchronize package metadata
to 0.2.0, and prove source/wheel artifacts work in clean environments.

## Module and test layout

- English configuration tutorials/reference live under `docs/`; equivalent
  Chinese documents live under `doc_cn/` and both indexes link them.
- Documentation and release checks live in
  `tests/config/test_documentation.py` and release scripts/tests.
- Any production edits obey the 200-line limit and full English rST docstrings
  for every callable and value class, including private ones.

## Contract

- Bilingual docs cover file grammar, includes, precedence, origins, errors,
  async loading, runtime conversion, lifecycle, limits, and trusted-input scope.
- Root READMEs contain independently executable 0.2 examples and clearly
  distinguish memory parsing from host-controlled include resolution.
- `pyproject.toml` and `pylcl.__version__` become exactly `0.2.0`; changelog and
  public API inventory match implemented behaviour without advertising CLI.
- Build wheel and sdist, inspect contents/metadata, install each with no
  dependencies in separate clean Python 3.14+ environments, then run config
  parse/load/evaluate smoke programs without repository imports.
- The release candidate requires strict mypy, Ruff, docstring/source-size checks,
  all tests with branch threshold, link/example checks, and a clean artifact diff.

## TDD matrix

- Sunny: execute bilingual examples and clean-install smoke tests from both
  artifacts.
- Rainy: structural checks fail for stale version, broken links, untranslated
  sections, undeclared exports, repository leakage, or advertised future CLI.
- Composite-complex: install the wheel, load a nested Unicode include graph via
  a host resolver, evaluate with stdlib, render provenance, and close the Frame.

## Completion evidence

`progress.md` records exact build/inspection/install/smoke/full-quality commands,
observed counts and coverage, artifact names/hashes, and completion date.
