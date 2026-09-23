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

The gate runs strict mypy over source, scripts and tests, and strict Pyright over
the focused public typing contracts in `tests/typing`. Both are development tools;
the installed library retains zero third-party runtime dependencies.

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
The PyPI version badge reads `info.version` from PyPI's project JSON through
Shields' dynamic JSON badge with a five-minute badge cache. It follows published
versions without editing the README; upstream PyPI and browser caches may add
delay. The standard Shields PyPI badge can retain a version for three hours.

Every push to the persistent `release` branch publishes its wheel and source
distribution to PyPI after the full quality gate and builds pass. Prepare a
new version in `pyproject.toml` and its changelog on `main`, then fast-forward
`release` to the tested commit and push it. The publishing gate fetches `main`
and rejects any commit that is not already in its history. It also requires a
nonempty dated changelog section matching the stable `1.0.x` package version;
manual tag builds must match that version, and an existing version tag must
point to the publishing commit.

After PyPI succeeds, CI creates the matching version tag and GitHub Release at
that exact commit, with the changelog notes and the same wheel and source
distribution attached. If this final step fails, rerun the failed job to finish
the GitHub Release without repeating the successful PyPI upload. Keep `release`
as a persistent branch, fast-forwarded from `main` for each version; do not add
release-only commits. PyPI versions are immutable: every
new release needs a new version. Existing-version uploads fail explicitly;
the workflow does not silently skip them or replace published files.

PyPI uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
with owner `gokurakujoudo`, repository `lclang`, workflow filename `ci.yml`, and
GitHub environment `pypi`. Register those values in the PyPI project's Publishing
settings. Configure the GitHub `pypi` environment to allow the `release` branch
and version tags. No PyPI username or password secret is needed. Only the upload
job can request an identity token; it downloads the already verified build
artifacts without checking out or executing project code. Uploads are serialized.

Manual publishing remains available: dispatch `ci.yml` with `publish=pypi`
on `release` or a version tag, or `publish=artifactory` on a tag. Other branches
cannot publish. A manual run with the default `publish=none` only verifies and
builds, even on `release`. Pull requests never publish. The selected ref must
contain this workflow, and the workflow must exist on the default branch for
manual dispatch. Artifactory still uses its matching GitHub environment,
`ARTIFACTORY_REPOSITORY_URL` variable, and `ARTIFACTORY_USERNAME` and
`ARTIFACTORY_PASSWORD` secrets.

See GitHub's [workflow triggering guide](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
for manual dispatch using a tag ref.

## Documentation publishing

The [documentation site](https://gokurakujoudo.github.io/lclang/) is served by
GitHub Pages, with the [Wiki](https://github.com/gokurakujoudo/lclang/wiki) as an
alternative view. Keep editing Markdown under `docs/`:
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

The site uses [MkDocs](https://www.mkdocs.org/) with its built-in Read the Docs
theme, configured in the root `mkdocs.yml`. MkDocs owns the page layout,
responsive navigation, breadcrumbs, previous/next links, and local search.
The small adapters under `scripts/` derive navigation from canonical Markdown,
resolve repository attachments at the built revision, and include the shared
logo and assets from `site/`. Existing `.html` page URLs are retained.

Tutorial navigation follows the series introduction, and the build rejects
pages missing from navigation. The package version comes from `pyproject.toml`.
The library still has no runtime dependencies; MkDocs, PyMdown Extensions,
Pygments, and markdown-it-py are documentation build dependencies only.

Labeled code fences receive Pygments colors at build time. `lcl` and `lclcfg`
use Python-style highlighting extended for LCL literals and operators; colors
are a reading aid, not syntax validation. Unknown, unlabeled, and `text` blocks
remain escaped plain text. A SuperFences adapter preserves the exact source,
including tabs and trailing blank lines, for selection and the Copy button.
Highlighting and navigation work without JavaScript; search and copying use
local scripts. No CDN, analytics, or external search service is required.
The Read the Docs theme uses its standard light reading surface.
Content fills the available width beside the sidebar with balanced horizontal
padding. Code blocks use one bordered surface, a compact Copy button, and
horizontal scrolling for long lines without widening the page.

Build and preview from the repository root:

```console
python -m pip install --group docs
python -m scripts.build_site
python -m mkdocs serve --dev-addr 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`. Both the wrapper and direct `python -m mkdocs build`
use strict validation. Site output must be a subdirectory of `build/`; generated
HTML is not checked in. `mkdocs serve` rebuilds changed Markdown for local preview.

CI builds and retains the `documentation-site` artifact on every verified run.
The CI `pages` job publishes that same artifact only after verification and
package builds pass, on pushes to the repository
variable `PAGES_SOURCE_BRANCH` (or the default branch when unset). During the
normal publishing this variable selects `main`. Pages uses the native GitHub
Actions deployment mechanism.

## Project logo

The canonical [PNG logo](../../site/assets/logo.png) lives in `site/assets/`.
The supplied artwork combines a blue, navy, and pale-blue geometric symbol
with the lclang wordmark on a light background.
Use the same asset above the home page content and in the favicon, README, and Wiki
home and sidebar. README images use the absolute Pages URL so the package
description also works on PyPI when a new distribution is published.

Keep the square proportions, original background, and surrounding clear space.
Browser icon assets use the same supplied PNG, scaled by the browser. The
wordmark is part of the image and needs no font or runtime dependency.
Asset provenance and usage are recorded alongside the logo.

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
