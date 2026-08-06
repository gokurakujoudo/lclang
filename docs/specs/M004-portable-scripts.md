# M004: portable project scripts

## Contract

Project automation is implemented in typed Python modules and invoked with the
active interpreter. The quality script runs pytest, mypy, Ruff, source policy,
and `git diff --check` in a stable fail-fast order. The build script creates
sdist and wheel artifacts through `python -m build`. The smoke script creates a
fresh virtual environment, installs one wheel without dependencies, imports
`pylcl`, verifies its version, and invokes its module entry point when one exists.

Paths must be constructed with `pathlib`; virtual-environment interpreter paths
must work on Windows and POSIX. Scripts never delete a caller-provided directory.

## Acceptance

- Unit tests lock command order and both virtual-environment path shapes.
- Every script offers a typed `main()` and exits with the child command status.
- The quality script passes on the current repository.
