# M052: JihuLab CI/CD pipeline

## Goal

Provide a GitLab-compatible pipeline for the JihuLab-hosted repository. The
pipeline must verify setup, build, test, and package inspection in one shared
job environment before a publish stage; publish the project's wheel and source
distribution to a local package Artifactory and to PyPI; and integrate Python
branch coverage with JihuLab's coverage views.

## Contract

- `.gitlab-ci.yml` declares the stages in the order `verify` and `publish`.
- The verification job installs the exact development dependency group from
  `pyproject.toml` once and verifies that the environment is internally consistent.
- Every direct build, test, type-check, lint, and publication tool is pinned to
  the locally verified version. CI consumes those groups instead of repeating
  version constraints, and pins its package installer to the local pip version.
- The same verification job uses `scripts.build_package`, retains exactly the
  versioned sdist and `py3-none-any` wheel, runs `scripts.quality`, inspects the
  packages, and converts coverage data to `coverage.xml` without creating a
  second container or reinstalling the development tools.
- The verification job exposes build and coverage outputs as downloadable
  artifacts plus a Cobertura `coverage_report`. Its `coverage` expression
  extracts the total percentage from the pytest-cov summary.
- The Artifactory and PyPI jobs are manual, tag-only publication gates. They
  require repository URLs and credentials from masked/protected JihuLab CI/CD
  variables and never store credentials in the repository.
- `PYPI_REPOSITORY_URL` defaults to PyPI's upload endpoint. The local
  `ARTIFACTORY_REPOSITORY_URL` is intentionally required from the project or
  group CI/CD variable configuration.

## TDD matrix

- Sunny: the structural pipeline checks find the shared verification environment,
  build artifacts, quality command, Cobertura report, coverage percentage
  extraction, and both tag-only manual publication jobs.
- Rainy: the checks reject a pipeline that omits the coverage report, makes a
  publication job run on a branch, or embeds a publication secret.
- Composite-complex: one verification job performs setup, build, quality,
  package inspection, and coverage reporting in order; its artifacts flow to
  Artifactory and PyPI while publication remains unavailable to non-tag pipelines.

## Verification boundary

Local tests validate the committed pipeline contract and YAML structure. An
actual JihuLab run is still required to verify runner image availability,
network access to the configured Artifactory, protected-variable policy, and
the credentials used by the project.
