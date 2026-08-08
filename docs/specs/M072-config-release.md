# M072: configuration documentation and 0.2 release gate

## Goal

Provide one user-friendly English tutorial path across installation, the
runtime, the complete expression language, and configuration files. Document
only the verified configuration surface, synchronize package metadata to
0.2.0, and prove source/wheel artifacts work in clean environments.

## Module and test layout

- `docs/tutorials/README.md`, `runtime.md`, `lcl_examples.md`, and
  `config_file.md` form the English beginner-to-advanced tutorial path.
- Detailed English references remain under `docs/`; existing Chinese API and
  configuration references remain under `doc_cn/`. Tutorial translation is a
  later documentation task, so no stale Chinese quickstart is retained.
- Tutorial, configuration, and release checks live in `tests/test_tutorials.py`,
  `tests/config/test_documentation.py`, and release scripts/tests.
- Any production edits obey the 200-line limit and full English rST docstrings
  for every callable and value class, including private ones.

## Contract

- The tutorial index covers installable artifacts, an independently executable
  three-minute workflow, and a table of contents for every tutorial.
- The runtime tutorial introduces Modules, Frames, lazy snapshots, hierarchy,
  host values, recalculation, dependencies, limits, and deterministic cleanup.
- The language gallery progresses from literals and operators through every V1
  form to fixed-point recursion, factorial, Fibonacci, and recursive quicksort.
- The configuration tutorial covers colon definitions, explicit continuation,
  magic values, using expansion, precedence, origins, errors, async loading,
  runtime conversion, lifecycle, limits, and trusted-input scope.
- The old user cheatsheet and English/Chinese runtime quickstarts are removed;
  all user-facing indexes link the new English tutorial path without dead links.
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

- Sunny: verify the tutorial table of contents, required concepts, language
  breadth, and install guidance; execute clean-install smoke tests from both
  artifacts.
- Rainy: structural checks fail for stale tutorial files, broken links, stale
  version, undeclared exports, repository leakage, or advertised future CLI.
- Composite-complex: execute every marked Python tutorial, parse every gallery
  expression, run fixed-point recursive programs, then install the wheel, load
  a nested Unicode using graph, evaluate with stdlib, render provenance, and
  close the Frame.

## Completion evidence

`progress.md` records exact build/inspection/install/smoke/full-quality commands,
observed counts and coverage, artifact names/hashes, and completion date.
