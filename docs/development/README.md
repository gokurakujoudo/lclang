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

The gate runs pytest with 100% branch coverage, strict mypy, Ruff, production
source-size and docstring policy, and whitespace checks. A focused test can be
run directly:

```console
venv\Scripts\python -m pytest tests/lang/parser/test_forms.py -q --no-cov
```

Additional release tools are available when needed:

```console
venv\Scripts\python -m scripts.security_audit
venv\Scripts\python -m scripts.performance_baseline
venv\Scripts\python -m scripts.release_candidate --output dist
```

## Change workflow

For a behavior change, update the relevant reference, add a practical failing
test, implement the smallest correct behavior, refactor, and run focused and
complete checks. Bugs require a reproducing test before the fix. Keep public
claims in the READMEs, changelog, and feature inventory synchronized.

Tests mirror production subsystem ownership. Reusable fixtures belong in
dedicated support modules. Mock external connectivity and isolate file I/O in a
per-test temporary directory.

See [Architecture and module layout](architecture.md) for package boundaries and
dependency direction.
