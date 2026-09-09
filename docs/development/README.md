# Local Development Guide

## Environment

Use Python 3.14 or newer. From the repository root:

```console
python -m venv venv
venv\Scripts\python -m pip install --group dev -e .
```

On POSIX systems, replace `venv\Scripts\python` with `venv/bin/python`.

## Test and quality commands

Run the complete project gate:

```console
venv\Scripts\python -m scripts.quality
```

The gate fails fast in this order: Git whitespace, Ruff, production source
policies, static architecture and capability constraints, strict mypy,
documentation checks without coverage, then all behavioral tests with 100%
production branch coverage. Source smoke, property and stress tests run by
default. A focused test can be run directly:

The CLI source smoke combines configuration inclusion, expression overrides,
derived evaluation, logging through `logger.file.app.directory`, and resource closure. It
uses static configuration fixtures and a separate `TemporaryDirectory`.

```console
venv\Scripts\python -m pytest tests/lang/parser/test_forms.py -q --no-cov
```

Architecture checks, optional performance measurements and explicit builds:

```console
venv\Scripts\python -m scripts.security_audit
venv\Scripts\python -m scripts.performance_baseline
venv\Scripts\python -m scripts.build_package --output dist
```

## GitHub CI and publishing

The repository is hosted at [gokurakujoudo/lclang](https://github.com/gokurakujoudo/lclang).
The `CI` GitHub Actions workflow verifies pushes and pull requests using the
same `scripts.quality` gate as local development. All runs build distributions
after verification; test reports, coverage and distributions are retained for seven days.

The quality gate writes `reports/tests-docs.xml` and `reports/tests-behavior.xml`
in JUnit XML format for test-result consumers. Behavioral tests also write
`reports/coverage.xml` (Cobertura), `reports/coverage.json`, and the browsable
`reports/htmlcov/index.html` report. The raw `.coverage` database uses relative
source paths so coverage.py can read it from another checkout of the same commit.
These generated files are ignored by Git.

Download `test-results` and `coverage` from a CI run's artifacts. Reports already
produced are uploaded even when verification fails. Because the gate fails fast,
a failure before pytest produces no test report, and a documentation failure
prevents behavioral reports from being generated. The README coverage badge
states the enforced 100% requirement; measured results are in each run's reports.

Publishing is explicit: dispatch `ci.yml` with a tag as the workflow ref and
the `publish` input set to `pypi` or `artifactory`. The default `none` only
verifies and builds. Publishing from a branch is rejected. The selected tag
must contain this workflow, and the workflow must also exist on the default
branch before manual dispatch is available. A manual run verifies and builds
the selected tag again before uploading its artifacts.

Configure the matching GitHub environment (`pypi` or `artifactory`) before
publishing. PyPI needs `PYPI_USERNAME` and `PYPI_PASSWORD` secrets. Artifactory
needs the `ARTIFACTORY_REPOSITORY_URL` variable and `ARTIFACTORY_USERNAME` and
`ARTIFACTORY_PASSWORD` secrets. Existing GitLab CI variables do not transfer
with Git history. No package is published by a push alone.

See GitHub's [workflow triggering guide](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
for manual dispatch using a tag ref.

## Documentation publishing

The [introduction site](https://gokurakujoudo.github.io/lclang/) is served by
GitHub Pages. The [Wiki](https://github.com/gokurakujoudo/lclang/wiki) is the
reader-facing documentation library. Keep editing Markdown under `docs/`:
it remains the canonical source and its marked examples run in the quality gate.
The Wiki export preserves those examples and rewrites local prose links into
Wiki navigation. Non-Markdown attachments link to the exact source revision.

CI exports all pages as the `wiki` artifact. To publish the current checked-out
documentation after quality checks, initialize the Wiki's Home page on GitHub
once, then use a separate Wiki checkout:

```console
git clone https://github.com/gokurakujoudo/lclang.wiki.git build/wiki-checkout
python -m scripts.export_wiki build/wiki-checkout
git -C build/wiki-checkout add --all
git -C build/wiki-checkout commit -m "Publish tested documentation"
git -C build/wiki-checkout push
```

Reuse an existing checkout on later updates, pulling before export. Generated
pages are overwritten; unrelated files are preserved. When retiring or renaming
a source page, remove its obsolete exported page in the Wiki checkout before
committing. The tutorial introduction remains the single ordered series index.
Wiki pushes use the maintainer's Git credentials; no personal token is stored
in the workflow. Direct Wiki edits should be made in `docs/` instead.

The dependency-free introduction lives in `site/`. The CI `pages` job publishes
it only after verification and package builds pass, on pushes to the repository
variable `PAGES_SOURCE_BRANCH` (or the default branch when unset). During the
hosting migration this variable selects `codex/impl`; switch it to `main` after
merging that branch. Pages uses the native GitHub Actions deployment mechanism.

## Change workflow

For a bug, update the relevant reference and prove a reproducing test fails
before fixing it. New features may use exploratory implementation, but acceptance
requires documentation and behavioral tests. Keep public claims in the root
README, changelog and feature inventory synchronized.

Before refactoring, run the existing tests. Change production code and pass those
tests before moving or consolidating tests; then verify the new organization.
Run affected checks while editing and the complete gate after each independent
code refactor and at final delivery. Pure prose changes need appropriate document
structure and link checks; changed examples must execute their exact source.
Tutorial structure changes run all documentation tests, without a mandatory
chapter/series/full-gate repetition.

Production files have a hard limit of 200 code-bearing physical lines, excluding
imports, declaration/attribute docstrings, pure comments and blanks. Standalone
strings outside documentation positions still count. Names must describe their behavior;
ordinary underscore-prefixed functions and classes are forbidden. Every production
function, including nested helpers, documents parameters, results and escaping
intentional exceptions in English rST. Constants need associated explanations of
units (or non-applicability), source, purpose and rationale; groups may share an
explanation. These policies apply to `src/lclang`; scripts and tests still run
through Ruff and mypy.

Static architecture scans enforce implementation constraints; they do not prove
that trusted configuration is a hostile-code sandbox. Builds are explicit local
operations or CI jobs after verification. Distribution archives contain
only downstream code, typing data, build metadata, the license and root README.

Tests mirror production subsystem ownership. Reusable fixtures belong in
dedicated support modules. Mock external connectivity and isolate file I/O in a
per-test temporary directory.

If permissions block a test or tool, stop the affected operation and request the
required permission. Do not move temporary files, change temporary-directory
environment variables, weaken isolation, skip checks or substitute another path
solely to bypass that failure without authorization. Continue independent work.

See [Architecture and module layout](architecture.md) for package boundaries and
dependency direction.
