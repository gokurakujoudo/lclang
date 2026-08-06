# M006: foundation release gate

## Contract

The project must produce one source distribution and one `py3-none-any` wheel
for version 0.0.0. The wheel contains the `pylcl` package and `py.typed`, declares
Python 3.14+, contains MIT metadata, and declares no runtime requirements.

A fresh virtual environment must install the wheel with `--no-deps` and import
`pylcl` as version 0.0.0. The build may create ignored artifacts but must not
rewrite tracked source or documentation.

## Acceptance

- The complete quality script passes immediately before building.
- `python -m scripts.build_package` succeeds.
- Wheel metadata and contents satisfy the contract.
- `python -m scripts.smoke_install <wheel>` succeeds.
- `git diff --check` remains clean after verification.
