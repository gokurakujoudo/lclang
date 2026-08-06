# M003: quality tooling

## Contract

The project uses Python-only development tools declared in a `dev` dependency
group. Pytest with branch coverage is the authoritative test runner. Mypy uses
strict mode, Ruff checks formatting and lint rules without rewriting files in
quality checks, and a project script verifies source-file length and public
docstrings.

Coverage measures `pylcl`, enables branch tracking, and fails below 99 percent.
Tests and tooling caches stay outside tracked source. Product modules may not
exceed 200 physical lines.

## Acceptance

- `pyproject.toml` declares pytest, pytest-cov, mypy, Ruff, and build tooling as
  development-only dependencies.
- Pytest, coverage, mypy, and Ruff have explicit checked-in configuration.
- A standard-library test proves the configured thresholds and strict options.
- Existing package tests pass through pytest with coverage enabled.
