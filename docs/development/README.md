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
operations or tag-pipeline jobs after verification. Distribution archives contain
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
