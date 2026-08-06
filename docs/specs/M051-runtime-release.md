# M051: 0.1 runtime release candidate

## Goal

Turn the completed and documented 0.1 expression/runtime surface into a verified
`0.1.0` source distribution and platform-independent wheel. The gate must prove
that both artifact paths work outside the repository on Python 3.14+ with no
runtime dependencies, without implementing configuration files, CLI behaviour,
or any new runtime feature.

This specification completes planning only. Version mutation, release tooling,
artifact creation, clean installation, and publication are implementation work
for a later M051 turn.

## Module and test layout

- Version metadata changes are limited to `pyproject.toml` and
  `pylcl/_version.py`; root `pylcl.__version__` continues re-exporting that one
  package value.
- Package construction continues through `scripts/build_package.py`. Artifact
  inspection belongs in `scripts/inspect_package.py`; isolated installation
  belongs in `scripts/smoke_install.py`; a small
  `scripts/release_candidate.py` may orchestrate the fail-fast sequence without
  duplicating checks.
- Release tests live under `tests/release/`: `test_metadata.py`,
  `test_artifacts.py`, `test_clean_install.py`, and a dedicated support module
  for artifact/venv fixtures. Existing package-script unit tests remain at their
  current subsystem boundaries unless behaviour genuinely moves.
- Planning acceptance remains in `tests/test_m051_specification.py`. It checks
  this contract and the `SPEC_READY` state; it is not evidence that the release
  implementation exists.
- Every added or changed Python function, method, and value class, including
  private helpers, must have the complete English rST docstring required by
  `AGENTS.md`. Python modules remain below 200 lines and all paths use
  `pathlib`.

## Public and metadata changes

- `[project].version` and `pylcl.__version__` become exactly `0.1.0` in the same
  implementation change. A mixed state is always a failing release candidate.
- `requires-python` remains `>=3.14`, the license remains MIT, distribution and
  import names remain `pylcl`, `py.typed` remains package data, and project
  metadata declares no runtime dependencies or optional runtime imports.
- The Trove development classifier advances from pre-alpha to
  `Development Status :: 3 - Alpha`; supported Python and typing classifiers
  remain accurate.
- The public symbol inventories of `pylcl`, `pylcl.lang`, `pylcl.ast`,
  `pylcl.runtime`, and `pylcl.stdlib` remain unchanged except for the value of
  `__version__`. M051 adds no configuration or CLI API.
- `CHANGELOG.md` gains an English `0.1.0` entry summarizing the implemented
  language/runtime, dependency tooling, standard preset, documentation, Python
  requirement, zero-dependency policy, and trusted-configuration security
  boundary. The changelog is included in the sdist.
- Only after every gate passes may `README.md` and `README_cn.md` say that 0.1.0
  is released, report the final observed test evidence, and point to the 0.1.0
  changelog entry. Until then their current unreleased wording remains correct.

## Artifact contract

- The release command requires a caller-selected output directory that is new or
  empty. It must not delete or overwrite an existing file, stale artifact, or
  caller directory to make the gate pass.
- A successful build produces exactly these two primary artifacts:
  `pylcl-0.1.0.tar.gz` and `pylcl-0.1.0-py3-none-any.whl`. Additional logs,
  extracted trees, or derived wheels live in a separate temporary verification
  directory and are not release artifacts.
- Wheel metadata reports name `pylcl`, version `0.1.0`, `Requires-Python:
  >=3.14`, MIT license metadata/text, no `Requires-Dist`, and the universal
  `py3-none-any` tag. The filename, `.dist-info` directory, METADATA, WHEEL, and
  imported version must agree.
- The wheel contains only the import package, `py.typed`, required wheel metadata,
  and license files. It excludes tests, scripts, docs, repository metadata,
  caches, bytecode, virtual environments, coverage data, and prior artifacts.
- The sdist contains the build metadata needed to build the wheel plus LICENSE,
  `CHANGELOG.md`, both root READMEs, `AGENTS.md`, `progress.md`, the English and
  Chinese documentation trees, package sources/`py.typed`, and the source tests
  declared by the existing source-distribution policy. It excludes ignored build
  output, virtual environments, caches, bytecode, coverage data, and VCS data.
- A second wheel is built from the unpacked sdist in an isolated directory and
  must satisfy the same filename, metadata, content-policy, and smoke contracts.
  Its archive hash need not equal the source-tree wheel across tools/platforms;
  semantic metadata and normalized member sets must match.
- After successful inspection and smoke tests, compute and record SHA-256 for the
  sdist and source-tree wheel. Hashes are evidence for the exact verified files,
  not a reproducible-build claim.

## Clean-install contract

- Verify the source-tree wheel and the sdist-derived wheel in separate fresh
  virtual environments. Installation uses `pip install --no-deps` and cannot
  resolve or install any runtime dependency.
- The sdist build environment may be provisioned with the build backend versions
  constrained in `pyproject.toml`. After that provisioning, sdist wheel creation
  and every runtime smoke step run with index/network access disabled.
- Smoke commands run with their working directory outside the repository,
  `PYTHONPATH` removed, no editable install, and no repository root inserted into
  `sys.path`. `pylcl.__file__` must resolve inside the fresh environment's
  site-packages, proving the checkout did not satisfy the import.
- Each installed artifact must report `pylcl.__version__ == "0.1.0"`, expose the
  documented root `__all__`, and retain `py.typed` beside installed package code.
- The installed sunny smoke uses `parse_expression` and `to_source` to parse and
  canonically print an LCL expression, evaluates one expression through both the
  async `evaluate` API and the synchronous `evaluate_sync` boundary, and checks
  structured syntax/name errors.
- The installed runtime smoke constructs a `Module`, combines `FrameFactory`
  with `STANDARD_PRESET`, evaluates strict JSON through a Frame, reads a
  `dependency_snapshot`, recalculates an owned definition, verifies cached
  dependant semantics, and awaits `close` with `frame.closed` true.
- The installed advanced smoke builds a dependency graph, obtains deterministic
  topological order, and calls at least one helper from each standard namespace:
  `iter`, `text`, `data`, and `json`.
- Smoke programs import no test/support module and use only documented public
  APIs. They print a fixed machine-checkable success record including version,
  artifact kind, evaluated value, dependency target, and closed state.

## Failure and state-safety contract

- Wrong or inconsistent versions, stale output, unexpected/missing archive
  members, wrong wheel tags, runtime requirements, metadata drift, missing
  license/type marker, repository import leakage, sdist rebuild failure, smoke
  mismatch, or any nonzero child process makes the gate fail.
- The orchestrator is fail-fast, returns the failing child status when available,
  and identifies the artifact and stage. It must not publish, upload, tag, commit,
  or mark M051 DONE. Publication is outside this milestone and requires separate
  user authorization.
- Tooling must not delete caller data, clean the repository, reset files, replace
  an existing output artifact, or hide a failure by selecting an older artifact.
  A non-empty output directory is rejected before building.
- Temporary environments/extractions are best-effort cleaned after success or
  ordinary failure. Cleanup failure is reported without erasing the primary
  failure. Caller-owned output and pre-existing files are never cleanup targets.
- Verification may create ignored artifacts and temporary directories, but it
  must not modify tracked files beyond the planned M051 version, changelog,
  documentation, test, and tooling changes. Record pre/post status and preserve
  unrelated user work.
- A failed release attempt leaves metadata at the deliberately implemented
  source state; it does not auto-revert files. The ledger remains below `DONE`
  until the complete gate is rerun successfully with coherent `0.1.0` metadata.
- Package installation does not make LCL a hostile-code sandbox. The artifacts
  retain the documented trusted-configuration security model.

## TDD matrix

- Sunny: update coherent 0.1.0 metadata, build the exact sdist/universal wheel,
  inspect normalized contents, build again from the sdist, and pass both isolated
  installed smoke suites with the fixed success record.
- Rainy: independently prove failures for version mismatch, non-empty output,
  wrong tag, injected dependency/member, missing license/`py.typed`, checkout
  import leakage, broken sdist rebuild, smoke error, and cleanup error; no case
  may publish, overwrite, delete caller data, or claim DONE.
- Composite-complex: from a path containing spaces and Unicode, build both
  artifacts, derive a wheel from the sdist with network disabled, install both
  outside the repository with `PYTHONPATH` absent, execute the complete
  parse/evaluate/FrameFactory/`STANDARD_PRESET`/dependency_snapshot/recalculate/
  close workflow, compare normalized artifact contracts, and record SHA-256.

## Completion evidence

Before implementation, `tests/test_m051_specification.py` must demonstrate RED
for the missing spec/status and then pass when planning is complete. This does
not advance M051 beyond `SPEC_READY`.

Implementation begins in a later turn with release behavioural tests proving
RED while source metadata still reports `0.0.0`. `DONE` requires all of the
following exact evidence in `progress.md`:

1. focused release tests with observed sunny/rainy/composite case counts;
2. `venv\Scripts\python.exe -m scripts.quality` with total tests, branch
   coverage, strict mypy, Ruff, source/docstring policy, and diff-check results;
3. the exact build/inspection/sdist-rebuild/clean-install commands and their
   zero statuses;
4. artifact filenames, byte sizes, SHA-256 values, normalized member audits,
   and verified METADATA fields;
5. fresh-environment Python version, resolved installed `pylcl.__file__`, fixed
   smoke records for both wheel paths, and confirmation that network/repository
   imports were unavailable;
6. synchronized `CHANGELOG.md`, `README.md`, `README_cn.md`, and this ledger,
   followed by a final quality/diff check and the verification date.
